from __future__ import print_function
import datetime
import json
import logging, os, sys
import boto3
from botocore.exceptions import ClientError
import pricecalculator.ec2.pricing as ec2pricing
import pricecalculator.rds.pricing as rdspricing
import pricecalculator.awslambda.pricing as lambdapricing

import pricecalculator.common.data as data


log = logging.getLogger()
log.setLevel(logging.INFO)

ec2client = None
rdsclient = None
elbclient = None
lambdaclient = None
cwclient = None
tagsclient = None

__location__ = os.path.dirname(os.path.realpath(__file__))
os.path.split(__location__)[0]
site_pkgs = os.path.join(os.path.split(__location__)[0], "lib", "python2.7", "site-packages")
sys.path.append(site_pkgs)


#_/_/_/_/_/_/ default_values - start _/_/_/_/_/_/

#Delay in minutes for metrics collection. We want to make sure that all metrics have arrived for the time period we are evaluating
#Note: Unless you have detailed metrics enabled in CloudWatch, make sure it is >= 10
METRIC_DELAY = 10

#Time window in minutes we will use for metric calculations
#Note: make sure this is at least 5, unless you have detailed metrics enabled in CloudWatch
METRIC_WINDOW = 5

FORECAST_PERIOD_MONTHLY = 'monthly'
FORECAST_PERIOD_HOURLY = 'hourly'
DEFAULT_FORECAST_PERIOD = FORECAST_PERIOD_MONTHLY
HOURS_DICT = {FORECAST_PERIOD_MONTHLY:720, FORECAST_PERIOD_HOURLY:1}


CW_NAMESPACE = 'ConcurrencyLabs/Pricing/NearRealTimeForecast'
CW_METRIC_NAME_ESTIMATEDCHARGES = 'EstimatedCharges'
CW_METRIC_DIMENSION_SERVICE_NAME = 'ServiceName'
CW_METRIC_DIMENSION_PERIOD = 'ForecastPeriod'
CW_METRIC_DIMENSION_CURRENCY = 'Currency'
CW_METRIC_DIMENSION_TAG = 'Tag'
CW_METRIC_DIMENSION_SERVICE_NAME_EC2 = 'ec2'
CW_METRIC_DIMENSION_SERVICE_NAME_RDS = 'rds'
CW_METRIC_DIMENSION_SERVICE_NAME_LAMBDA = 'lambda'
CW_METRIC_DIMENSION_SERVICE_NAME_TOTAL = 'total'
CW_METRIC_DIMENSION_CURRENCY_USD = 'USD'


SERVICE_EC2 = 'ec2'
SERVICE_RDS = 'rds'
SERVICE_ELB = 'elasticloadbalancing'
SERVICE_LAMBDA = 'lambda'

RESOURCE_LAMBDA_FUNCTION = 'function'
RESOURCE_ELB = 'loadbalancer'
RESOURCE_EC2_INSTANCE = 'instance'
RESOURCE_RDS_DB_INSTANCE = 'db'
RESOURCE_EBS_VOLUME = 'volume'
RESOURCE_EBS_SNAPSHOT = 'snapshot'

SERVICE_RESOURCE_MAP = {SERVICE_EC2:[RESOURCE_EBS_VOLUME,RESOURCE_EBS_SNAPSHOT, RESOURCE_EC2_INSTANCE],
                        SERVICE_RDS:[RESOURCE_RDS_DB_INSTANCE],
                        SERVICE_LAMBDA:[RESOURCE_LAMBDA_FUNCTION],
                        SERVICE_ELB:[RESOURCE_ELB]}


#_/_/_/_/_/_/ default values - end _/_/_/_/_/_/



"""
Limitations (features not yet available):
    - Calculates all NetworkOut metrics as 'out to the internet', since there is no way to know in near real-time
      with CloudWath metrics the bytes destination. This would only be possible using VPC Flow Logs, which are not
      available in near real-time.
"""

def handler(event, context):
    log.info("Received event {}".format(json.dumps(event)))

    init_clients(context)

    result = {}
    pricing_records = []
    ec2Cost = 0
    rdsCost = 0
    lambdaCost = 0
    totalCost = 0

    #First, get the tags we'll be searching for, from the CloudWatch scheduled event
    #TODO: add support for multiple tags in a single event (beware this could increase function execution time)
    #TODO: add support for lambda function qualifiers in CW Event.
    tagkey = ""
    tagvalue = ""
    if 'tag' in event:
      tagkey = event['tag']['key']
      tagvalue = event['tag']['value']
      if tagkey == "" or tagvalue == "":
          log.error("No tags specified, aborting function!")
          return {}

      log.info("Will search resources with the following tag:["+tagkey+"] - value["+tagvalue+"]")

    resource_manager = ResourceManager(tagkey, tagvalue)

    lambdafunctions = resource_manager.get_resources(SERVICE_LAMBDA, RESOURCE_LAMBDA_FUNCTION)

    start, end = calculate_time_range()

    elb_hours = 0
    elb_data_processed_gb = 0
    elb_instances = {}

    #Get tagged ELB(s) and their registered instances
    #taggedelbs = find_elbs(tagkey, tagvalue)
    taggedelbs = resource_manager.get_resource_ids(SERVICE_ELB, RESOURCE_ELB)
    if taggedelbs:
        log.info("Found tagged ELBs:{}".format(taggedelbs))
        elb_hours = len(taggedelbs)*HOURS_DICT[DEFAULT_FORECAST_PERIOD]
        elb_instances = get_elb_instances(taggedelbs)
        #Get all EC2 instances registered with each tagged ELB, so we can calculate ELB data processed
        #Registered instances will be used for data processed calculation, and not for instance hours, unless they're tagged.
        if elb_instances:
          log.info("Found registered EC2 instances to tagged ELBs [{}]:{}".format(taggedelbs, elb_instances.keys()))
          elb_data_processed_gb = calculate_elb_data_processed(start, end, elb_instances)*calculate_forecast_factor() / (10**9)
        else:
          log.info("Didn't find any EC2 instances registered to tagged ELBs [{}]".format(taggedelbs))
    else:
        log.info("No tagged ELBs found")

    #Get tagged EC2 instances
    ec2_instances = get_ec2_instances_by_tag(tagkey, tagvalue)
    if ec2_instances:
        log.info("Tagged EC2 instances:{}".format(ec2_instances.keys()))
    else:
        log.info("Didn't find any tagged, running EC2 instances")

    #Calculate ELB cost
    if elb_hours:
        elb_cost = ec2pricing.calculate(data.Ec2PriceDimension(region=region, elbHours=elb_hours,elbDataProcessedGb=elb_data_processed_gb))
        if 'pricingRecords' in elb_cost:
            pricing_records.extend(elb_cost['pricingRecords'])
            ec2Cost = ec2Cost + elb_cost['totalCost']

    #Calculate EC2 compute time for ALL instance types found (subscribed to ELB or not) - group by instance types
    all_instance_dict = {}
    all_instance_dict.update(ec2_instances)
    all_instance_types = get_instance_type_count(all_instance_dict)
    log.info("All instance types:{}".format(all_instance_types))


    #Calculate EC2 compute time cost
    for instance_type in all_instance_types:
        ec2_compute_cost = ec2pricing.calculate(data.Ec2PriceDimension(region=region, instanceType=instance_type, instanceHours=all_instance_types[instance_type]*HOURS_DICT[DEFAULT_FORECAST_PERIOD]))
        if 'pricingRecords' in ec2_compute_cost: pricing_records.extend(ec2_compute_cost['pricingRecords'])
        ec2Cost = ec2Cost + ec2_compute_cost['totalCost']

    #Get provisioned storage by volume type, and provisioned IOPS (if applicable)
    ebs_storage_dict, piops = get_storage_by_ebs_type(all_instance_dict)

    #Calculate EBS storagecost
    for k in ebs_storage_dict.keys():
        if k == 'io1': pricing_piops = piops
        else: pricing_piops = 0

        ebs_storage_cost = ec2pricing.calculate(data.Ec2PriceDimension(region=region, ebsVolumeType=k, ebsStorageGbMonth=ebs_storage_dict[k], pIops=pricing_piops))
        if 'pricingRecords' in ebs_storage_cost: pricing_records.extend(ebs_storage_cost['pricingRecords'])
        ec2Cost = ec2Cost + ebs_storage_cost['totalCost']

    #Get total snapshot storage
    #Will remove this functionality, since EBS Snapshot usage cannot be accurately calculated from the EC2 API
    """
    snapshot_gb_month = get_total_snapshot_storage(tagkey, tagvalue)
    ebs_snapshot_cost = {}
    if snapshot_gb_month:
      ebs_snapshot_cost = ec2pricing.calculate(data.Ec2PriceDimension(region=region, ebsSnapshotGbMonth=snapshot_gb_month))
      if 'pricingRecords' in ebs_snapshot_cost: pricing_records.extend(ebs_snapshot_cost['pricingRecords'])
      ec2Cost = ec2Cost + ebs_snapshot_cost['totalCost']
    else:
      log.info("Didn't find any tagged EBS snapshots")
    """


    #Get tagged RDS DB instances
    #db_instances = get_db_instances_by_tag(tagkey, tagvalue)
    db_instances = get_db_instances_by_tag(resource_manager.get_resource_ids(SERVICE_RDS, RESOURCE_RDS_DB_INSTANCE))
    if db_instances:
        log.info("Found the following tagged DB instances:{}".format(db_instances.keys()))
    else:
        log.info("Didn't find any tagged DB instances")

    #Calculate RDS instance time for ALL instance types found - group by DB instance types
    all_db_instance_dict = {}
    all_db_instance_dict.update(db_instances)
    all_db_instance_types = get_db_instance_type_count(all_db_instance_dict)
    all_db_storage_types = get_db_storage_type_count(all_db_instance_dict)

    #Calculate RDS instance time cost
    rds_instance_cost = {}
    for db_instance_type in all_db_instance_types:
        dbInstanceClass = db_instance_type.split("|")[0]
        engine = db_instance_type.split("|")[1]
        licenseModel= db_instance_type.split("|")[2]
        multiAz= bool(int(db_instance_type.split("|")[3]))
        log.info("Calculating RDS DB Instance compute time")
        rds_instance_cost = rdspricing.calculate(data.RdsPriceDimension(region=region, dbInstanceClass=dbInstanceClass, multiAz=multiAz,
                                        engine=engine, licenseModel=licenseModel, instanceHours=all_db_instance_types[db_instance_type]*HOURS_DICT[DEFAULT_FORECAST_PERIOD]))

        if 'pricingRecords' in rds_instance_cost: pricing_records.extend(rds_instance_cost['pricingRecords'])
        rdsCost = rdsCost + rds_instance_cost['totalCost']

    #Calculate RDS storage cost
    rds_storage_cost = {}
    for storage_key in all_db_storage_types.keys():
        storageType = storage_key.split("|")[0]
        multiAz = bool(int(storage_key.split("|")[1]))
        storageGbMonth = all_db_storage_types[storage_key]['AllocatedStorage']
        iops = all_db_storage_types[storage_key]['Iops']
        log.info("Calculating RDS DB Instance Storage")
        rds_storage_cost = rdspricing.calculate(data.RdsPriceDimension(region=region, storageType=storageType,
                                                                        multiAz=multiAz, storageGbMonth=storageGbMonth,
                                                                        iops=iops))

        if 'pricingRecords' in rds_storage_cost: pricing_records.extend(rds_storage_cost['pricingRecords'])
        rdsCost = rdsCost + rds_storage_cost['totalCost']

    #RDS Data Transfer - the Lambda function will assume all data transfer happens between RDS and EC2 instances

    #Lambda functions
    for func in lambdafunctions:
      executions = calculate_lambda_executions(start, end, func)
      avgduration = calculate_lambda_duration(start, end, func)
      funcname = ''
      qualifier = ''
      fullname = ''
      funcname = func.id
      fullname = funcname
      #if 'qualifier' in func:
      #    qualifier = func['qualifier']
      #    fullname += ":"+qualifier
      memory = get_lambda_memory(funcname,qualifier)
      log.info("Executions for Lambda function [{}]: [{}] - Memory:[{}] - Avg Duration:[{}]".format(funcname,executions,memory, avgduration))
      if executions and avgduration:
          #Note we're setting data transfer = 0, since we don't have a way to calculate it based on CW metrics alone
          lambdapdim = data.LambdaPriceDimension(region=region, requestCount=executions*calculate_forecast_factor(),
                                            avgDurationMs=avgduration, memoryMb=memory, dataTranferOutInternetGb=0,
                                            dataTranferOutIntraRegionGb=0, dataTranferOutInterRegionGb=0, toRegion='')
          lambda_func_cost = lambdapricing.calculate(lambdapdim)
          if 'pricingRecords' in lambda_func_cost: pricing_records.extend(lambda_func_cost['pricingRecords'])
          lambdaCost = lambdaCost + lambda_func_cost['totalCost']

          put_cw_metric_data(end, lambda_func_cost['totalCost'], CW_METRIC_DIMENSION_SERVICE_NAME_LAMBDA, 'function-name' , fullname)
      else:
          log.info("Skipping pricing calculation for function [{}] - qualifier [{}] due to lack of executions in [{}-minute] time window".format(fullname, qualifier, METRIC_WINDOW))


    #Do this after all calculations for all supported services have concluded
    totalCost = ec2Cost + rdsCost + lambdaCost
    result['pricingRecords'] = pricing_records
    result['totalCost'] = round(totalCost,2)
    result['forecastPeriod']=DEFAULT_FORECAST_PERIOD
    result['currency'] = CW_METRIC_DIMENSION_CURRENCY_USD

    #Publish metrics to CloudWatch using the default namespace

    if tagkey:
      put_cw_metric_data(end, ec2Cost, CW_METRIC_DIMENSION_SERVICE_NAME_EC2, tagkey, tagvalue)
      put_cw_metric_data(end, rdsCost, CW_METRIC_DIMENSION_SERVICE_NAME_RDS, tagkey, tagvalue)
      put_cw_metric_data(end, lambdaCost, CW_METRIC_DIMENSION_SERVICE_NAME_LAMBDA, tagkey, tagvalue)
      put_cw_metric_data(end, totalCost, CW_METRIC_DIMENSION_SERVICE_NAME_TOTAL, tagkey, tagvalue)


    log.info (json.dumps(result,sort_keys=False,indent=4))

    return result

#TODO: calculate data transfer for instances that are not registered with the ELB
#TODO: Support different OS for EC2 instances (see how engine and license combinations are calculated for RDS)
#TODO: log the actual AWS resources that are found for the price calculation
#TODO: add support for detailed metrics fee
#TODO: add support for EBS optimized
#TODO: add support for EIP
#TODO: add support for EC2 operating systems other than Linux
#TODO: calculate monthly hours based on the current month, instead of assuming 720
#TODO: add support for different forecast periods (1 hour, 1 day, 1 month, etc.)
#TODO: add support for Spot and Reserved. Function only supports On-demand instances at the time


def put_cw_metric_data(timestamp, cost, service, tagkey, tagvalue):

    response = cwclient.put_metric_data(
        Namespace=CW_NAMESPACE,
        MetricData=[
            {
                'MetricName': CW_METRIC_NAME_ESTIMATEDCHARGES,
                'Dimensions': [{'Name': CW_METRIC_DIMENSION_SERVICE_NAME,'Value': service},
                               {'Name': CW_METRIC_DIMENSION_PERIOD,'Value': DEFAULT_FORECAST_PERIOD},
                               {'Name': CW_METRIC_DIMENSION_CURRENCY,'Value': CW_METRIC_DIMENSION_CURRENCY_USD},
                               {'Name': CW_METRIC_DIMENSION_TAG,'Value': tagkey+'='+tagvalue}
                ],
                'Timestamp': timestamp,
                'Value': cost,
                'Unit': 'Count'
            }
        ]
    )


def get_elb_instances(elbnames):
    result = {}
    instance_ids = []
    elbs = elbclient.describe_load_balancers(LoadBalancerNames=elbnames)
    if 'LoadBalancerDescriptions' in elbs:
        for e in elbs['LoadBalancerDescriptions']:
            if 'Instances' in e:
              instances = e['Instances']
              for i in instances:
                  instance_ids.append(i['InstanceId'])

    if instance_ids:
        response = ec2client.describe_instances(InstanceIds=instance_ids)
        if 'Reservations' in response:
            for r in response['Reservations']:
                if 'Instances' in r:
                    for i in r['Instances']:
                        result[i['InstanceId']]=i

    return result


def get_ec2_instances_by_tag(tagkey, tagvalue):
    result = {}
    response = ec2client.describe_instances(Filters=[{'Name': 'tag:'+tagkey, 'Values':[tagvalue]},
                                                     {'Name': 'instance-state-name', 'Values': ['running',]}])
    if 'Reservations' in response:
        reservations = response['Reservations']
        for r in reservations:
            if 'Instances' in r:
                for i in r['Instances']:
                    result[i['InstanceId']]=i

    return result



def get_db_instances_by_tag(dbIds):
    result = {}
    #TODO: paginate
    if dbIds:
        response = rdsclient.describe_db_instances(Filters=[{'Name':'db-instance-id','Values':dbIds}])
        if 'DBInstances' in response:
            dbInstances = response['DBInstances']
            for d in dbInstances:
                result[d['DbiResourceId']]=d
    return result



def get_non_elb_instances_by_tag(tagkey, tagvalue, elb_instances):
    result = {}
    response = ec2client.describe_instances(Filters=[{'Name': 'tag:'+tagkey, 'Values':[tagvalue]}])
    if 'Reservations' in response:
        reservations = response['Reservations']
        for r in reservations:
            if 'Instances' in r:
                for i in r['Instances']:
                    if i['InstanceId'] not in elb_instances: result[i['InstanceId']]=i

    return result

def get_instance_type_count(instance_dict):
    result = {}
    for key in instance_dict:
        instance_type = instance_dict[key]['InstanceType']
        if instance_type in result:
            result[instance_type] = result[instance_type] + 1
        else:
            result[instance_type] = 1
    return result


def get_db_instance_type_count(db_instance_dict):
    result = {}
    for key in db_instance_dict:
        #key format: db-instance-class|engine|license-model|multi-az
        multiAz = 0
        if db_instance_dict[key]['MultiAZ']==True:multiAz=1
        db_instance_key = db_instance_dict[key]['DBInstanceClass']+"|"+\
                          db_instance_dict[key]['Engine']+"|"+\
                          db_instance_dict[key]['LicenseModel']+"|"+\
                          str(multiAz)
        if db_instance_key in result:
            result[db_instance_key] = result[db_instance_key] + 1
        else:
            result[db_instance_key] = 1
    return result


def get_db_storage_type_count(db_instance_dict):
    result = {}
    for key in db_instance_dict:
        #key format: db-storage-type|allocated-storage|iops|multi-az
        multiAz = 0
        #print("db_instance_dict[{}]".format(db_instance_dict[key]))
        if db_instance_dict[key]['MultiAZ']==True:multiAz=1
        db_storage_key = db_instance_dict[key]['StorageType']+"|"+\
                          str(multiAz)

        if 'Iops' not in db_instance_dict[key]: db_instance_dict[key]['Iops'] = 0

        if db_storage_key in result:
            result[db_storage_key]['Iops'] += db_instance_dict[key]['Iops']
            result[db_storage_key]['AllocatedStorage'] += db_instance_dict[key]['AllocatedStorage']
        else:
            result[db_storage_key] = {}
            result[db_storage_key]['Iops'] = db_instance_dict[key]['Iops']
            result[db_storage_key]['AllocatedStorage'] = db_instance_dict[key]['AllocatedStorage']

        #print ("Storage composite key:[{}]".format(db_storage_key))


    return result




def get_storage_by_ebs_type(instance_dict):
    result = {}
    iops = 0
    ebs_ids = []
    for key in instance_dict:
        block_mappings = instance_dict[key]['BlockDeviceMappings']
        for bm in block_mappings:
            if 'Ebs' in bm:
                if 'VolumeId' in bm['Ebs']:
                    ebs_ids.append(bm['Ebs']['VolumeId'])

    volume_details = {}
    if ebs_ids: volume_details = ec2client.describe_volumes(VolumeIds=ebs_ids)#TODO:add support for pagination
    if 'Volumes' in volume_details:
        for v in volume_details['Volumes']:
            volume_type = v['VolumeType']
            if volume_type in result:
                result[volume_type] = result[volume_type] + int(v['Size'])
            else:
                result[volume_type] = int(v['Size'])
            if volume_type == 'io1': iops = iops + int(v['Iops'])

    return result, iops


def get_total_snapshot_storage(tagkey, tagvalue):
    result = 0
    snapshots = ec2client.describe_snapshots(Filters=[{'Name': 'tag:'+tagkey,'Values': [tagvalue]}])
    if 'Snapshots' in snapshots:
        for s in snapshots['Snapshots']:
            result = result + s['VolumeSize']

    #log.info("total snapshot size:["+str(result)+"]")
    return result




"""
For each EC2 instance registered to an ELB, get the following metrics: NetworkIn, NetworkOut.
Then add them up and use them to calculate the total data processed by the ELB
"""
def calculate_elb_data_processed(start, end, elb_instances):
    result = 0

    for instance_id in elb_instances.keys():
        metricsNetworkIn = cwclient.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName='NetworkIn',
            Dimensions=[{'Name': 'InstanceId','Value': instance_id}],
            StartTime=start,
            EndTime=end,
            Period=60*METRIC_WINDOW,
            Statistics = ['Sum']
        )
        metricsNetworkOut = cwclient.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName='NetworkOut',
            Dimensions=[{'Name': 'InstanceId','Value': instance_id}],
            StartTime=start,
            EndTime=end,
            Period=60*METRIC_WINDOW,
            Statistics = ['Sum']
        )
        for datapoint in metricsNetworkIn['Datapoints']:
            if 'Sum' in datapoint: result = result + datapoint['Sum']
        for datapoint in metricsNetworkOut['Datapoints']:
            if 'Sum' in datapoint: result = result + datapoint['Sum']

    log.info ("Total Bytes processed by ELBs in time window of ["+str(METRIC_WINDOW)+"] minutes :["+str(result)+"]")

    return result



def calculate_lambda_executions(start, end, func):
    result = 0

    invocations = cwclient.get_metric_statistics(
            Namespace='AWS/Lambda',
            MetricName='Invocations',
            #Dimensions=[{'Name': 'FunctionName','Value': func['name']}],
            Dimensions=[{'Name': 'FunctionName','Value': func.id}],
            StartTime=start,
            EndTime=end,
            Period=60*METRIC_WINDOW,
            Statistics = ['Sum']
        )
    for datapoint in invocations['Datapoints']:
      if 'Sum' in datapoint: result = result + datapoint['Sum']

    log.debug("calculate_lambda_executions: [{}]".format(result))
    return result


def calculate_lambda_duration(start, end, func):
    result = 0

    invocations = cwclient.get_metric_statistics(
            Namespace='AWS/Lambda',
            MetricName='Duration',
            #Dimensions=[{'Name': 'FunctionName','Value': func['name']}],
            Dimensions=[{'Name': 'FunctionName','Value': func.id}],
            StartTime=start,
            EndTime=end,
            Period=60*METRIC_WINDOW,
            Statistics = ['Average']
        )
    count = 0
    total = 0
    for datapoint in invocations['Datapoints']:
      if 'Average' in datapoint:
          count+=1
          total+=datapoint['Average']

    if count: result = total / count

    log.debug("calculate_lambda_duration: [{}]".format(result))

    return result


def get_lambda_memory(functionname, qualifier):
    result = 0
    args = {}
    if qualifier: args = {'FunctionName':functionname,'Qualifier':qualifier}
    else: args = {'FunctionName':functionname}
    try:
        response = lambdaclient.get_function_configuration(**args)
        if 'MemorySize' in response:
            result = response['MemorySize']

    except ClientError as e:
        log.error("{}".format(e))

    return result




def calculate_time_range():
    start = datetime.datetime.utcnow() + datetime.timedelta(minutes=-METRIC_DELAY)
    end = start + datetime.timedelta(minutes=METRIC_WINDOW)
    log.info("start:["+str(start)+"] - end:["+str(end)+"]")
    return start, end



def calculate_forecast_factor():
    result = (60 / METRIC_WINDOW ) * HOURS_DICT[DEFAULT_FORECAST_PERIOD]
    log.debug("Forecast factor:["+str(result)+"]")
    return result


def get_ec2_instances(registered, all):
    result = []
    for a in all:
        if a not in registered: result.append(a)
    return result


def init_clients(context):
    global ec2client
    global rdsclient
    global elbclient
    global lambdaclient
    global cwclient
    global tagsclient
    global region
    global awsaccount

    arn = context.invoked_function_arn
    region = arn.split(":")[3] #ARN format is arn:aws:lambda:us-east-1:xxx:xxxx
    awsaccount = arn.split(":")[4]
    ec2client = boto3.client('ec2',region)
    rdsclient = boto3.client('rds',region)
    elbclient = boto3.client('elb',region)
    lambdaclient = boto3.client('lambda',region)
    cwclient = boto3.client('cloudwatch', region)
    tagsclient = boto3.client('resourcegroupstaggingapi', region)


class ResourceManager():
    def __init__(self, tagkey, tagvalue):
        self.resources = []
        self.init_resources(tagkey, tagvalue)


    def init_resources(self, tagkey, tagvalue):
        #TODO: Implement pagination
        response = tagsclient.get_resources(
                            TagsPerPage = 500,
                            TagFilters=[{'Key': tagkey,'Values': [tagvalue]}],
                            ResourceTypeFilters=self.get_resource_type_filters(SERVICE_RESOURCE_MAP)
                    )

        if 'ResourceTagMappingList' in response:
            for r in response['ResourceTagMappingList']:
                res = self.extract_resource(r['ResourceARN'])
                if res:
                    self.resources.append(res)
                    log.info("Tagged resource:{}".format(res.__dict__))

    #Return a service:resource list in the format the ResourceGroupTagging API expects it
    def get_resource_type_filters(self, service_resource_map):
        result = []
        for s in service_resource_map.keys():
            for r in service_resource_map[s]: result.append("{}:{}".format(s,r))
        return result


    def extract_resource(self, arn):
        service = arn.split(":")[2]
        resourceId = ''
        #See http://docs.aws.amazon.com/general/latest/gr/aws-arns-and-namespaces.html for different patterns in ARNs
        for service in ('ec2', 'elasticloadbalancing'):
            for type in ('instance','volume','snapshot','loadbalancer'):
                if ':'+service+':' in arn and ':'+type+'/' in arn:
                    resourceId = arn.split(':'+type+'/')[1]
                    return self.Resource(service, type, resourceId, arn)
        for service in ('rds', 'lambda'):
            for type in ('db', 'function'):
                if ':'+service+':' in arn and ':'+type+':' in arn:
                    resourceId = arn.split(':'+type+':')[1]
                    return self.Resource(service, type, resourceId, arn)

        return None

    def get_resources(self, service, resourceType):
        result = []
        if self.resources:
            for r in self.resources:
                if r.service == service and r.type == resourceType:
                    result.append(r)
        return result


    def get_resource_ids(self, service, resourceType):
        result = []
        if self.resources:
            for r in self.resources:
                if r.service == service and r.type == resourceType:
                    result.append(r.id)
        return result




    class Resource():
        def __init__(self, service, type, id, arn):
            self.service = service
            self.type = type
            self.id = id
            self.arn = arn



















