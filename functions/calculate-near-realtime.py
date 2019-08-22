from __future__ import print_function
import datetime
import json
import logging,traceback
import math
import os
import sys


import boto3
from botocore.exceptions import ClientError


__location__ = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(__location__, "../"))
sys.path.append(os.path.join(__location__, "../vendored"))


import awspricecalculator.ec2.pricing as ec2pricing
import awspricecalculator.rds.pricing as rdspricing
import awspricecalculator.awslambda.pricing as lambdapricing
import awspricecalculator.dynamodb.pricing as ddbpricing
import awspricecalculator.kinesis.pricing as kinesispricing
import awspricecalculator.common.models as data
import awspricecalculator.common.consts as consts
from awspricecalculator.common.errors import NoDataFoundError

log = logging.getLogger()
#log.setLevel(logging.INFO)



ec2client = None
rdsclient = None
elbclient = None
lambdaclient = None
dddbclient = None
kinesisclient = None
cwclient = None
tagsclient = None

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
CW_METRIC_DIMENSION_SERVICE_NAME_DYNAMODB = 'dynamodb'
CW_METRIC_DIMENSION_SERVICE_NAME_KINESIS = 'kinesis'
CW_METRIC_DIMENSION_SERVICE_NAME_TOTAL = 'total'
CW_METRIC_DIMENSION_CURRENCY_USD = 'USD'


SERVICE_EC2 = 'ec2'
SERVICE_RDS = 'rds'
SERVICE_ELB = 'elasticloadbalancing'
SERVICE_LAMBDA = 'lambda'
SERVICE_DYNAMODB = 'dynamodb'
SERVICE_KINESIS = 'kinesis'

RESOURCE_LAMBDA_FUNCTION = 'function'
RESOURCE_ELB = 'loadbalancer'
RESOURCE_ALB = 'loadbalancer/app'
RESOURCE_NLB = 'loadbalancer/net'
RESOURCE_EC2_INSTANCE = 'instance'
RESOURCE_RDS_DB_INSTANCE = 'db'
RESOURCE_EBS_VOLUME = 'volume'
RESOURCE_EBS_SNAPSHOT = 'snapshot'
RESOURCE_DDB_TABLE = 'table'
RESOURCE_STREAM = 'stream'

#This map is used to specify which services and resource types will be searched using the tag service
SERVICE_RESOURCE_MAP = {SERVICE_EC2:[RESOURCE_EBS_VOLUME,RESOURCE_EBS_SNAPSHOT, RESOURCE_EC2_INSTANCE],
                        SERVICE_RDS:[RESOURCE_RDS_DB_INSTANCE],
                        SERVICE_LAMBDA:[RESOURCE_LAMBDA_FUNCTION],
                        SERVICE_ELB:[RESOURCE_ELB], #only provide RESOURCE_ELB, even for ALB and NLB
                        SERVICE_DYNAMODB:[RESOURCE_DDB_TABLE],
                        SERVICE_KINESIS:[RESOURCE_STREAM]
                        }

#_/_/_/_/_/_/ default values - end _/_/_/_/_/_/


def handler(event, context):
    log.setLevel(consts.LOG_LEVEL)
    log.info("Received event {}".format(json.dumps(event)))

    try:
        init_clients(context)

        result = {}
        pricing_records = []
        ec2Cost = 0
        rdsCost = 0
        lambdaCost = 0
        ddbCost = 0
        kinesisCost = 0
        totalCost = 0


        #First, get the tags we'll be searching for, from the CloudWatch scheduled event
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

        start, end = calculate_time_range()

        elb_hours = 0
        elb_data_processed_gb = 0
        elb_instances = {}
        alb_hours = 0
        alb_lcus = 0

        #Get tagged ELB(s) and their registered instances
        #taggedelbs = find_elbs(tagkey, tagvalue)
        taggedelbs = resource_manager.get_resource_ids(SERVICE_ELB, RESOURCE_ELB)
        taggedalbs = resource_manager.get_resource_ids(SERVICE_ELB, RESOURCE_ALB)
        taggednlbs = resource_manager.get_resource_ids(SERVICE_ELB, RESOURCE_NLB)
        if taggedelbs:
            log.info("Found tagged Classic ELBs:{}".format(taggedelbs))
            elb_instances = get_elb_instances(taggedelbs)#TODO:add support to find registered instances for ALB and NLB
            #Get all EC2 instances registered with each tagged ELB, so we can calculate ELB data processed
            #Registered instances will be used for data processed calculation, and not for instance hours, unless they're tagged.
        if taggedalbs:
            log.info("Found tagged Application Load Balancers:{}".format(taggedalbs))
        if taggednlbs:
            log.info("Found tagged Network Load Balancers:{}".format(taggednlbs))

        #TODO: once pricing for ALB and NLB is added to awspricecalculator, separate hours by ELB type
        elb_hours += (len(taggedelbs)+len(taggednlbs))*HOURS_DICT[DEFAULT_FORECAST_PERIOD]
        alb_hours += len(taggedalbs)*HOURS_DICT[DEFAULT_FORECAST_PERIOD]


        if elb_instances:
            try:
                log.info("Found registered EC2 instances to tagged ELBs [{}]:{}".format(taggedelbs, elb_instances.keys()))
                elb_data_processed_gb = calculate_elb_data_processed(start, end, elb_instances)*calculate_forecast_factor() / (10**9)
            except Exception as failure:
                log.error('Error calculating costs for tagged ELBs: %s', failure)
        else:
          log.info("Didn't find any EC2 instances registered to tagged ELBs [{}]".format(taggedelbs))
        #else:
        #    log.info("No tagged ELBs found")

        #Get tagged EC2 instances
        ec2_instances = get_ec2_instances_by_tag(tagkey, tagvalue)
        if ec2_instances:
            log.info("Tagged EC2 instances:{}".format(ec2_instances.keys()))
        else:
            log.info("Didn't find any tagged, running EC2 instances")

        #Calculate Classic ELB cost
        if elb_hours:
            elb_cost = ec2pricing.calculate(data.Ec2PriceDimension(region=region, elbHours=elb_hours,elbDataProcessedGb=elb_data_processed_gb))
            if 'pricingRecords' in elb_cost:
                pricing_records.extend(elb_cost['pricingRecords'])
                ec2Cost = ec2Cost + elb_cost['totalCost']

        #Calculate Application Load Balancer cost
        if alb_hours:
            alb_lcus = calculate_alb_lcus(start, end, taggedalbs)*calculate_forecast_factor()
            alb_cost = ec2pricing.calculate(data.Ec2PriceDimension(region=region, albHours=alb_hours, albLcus=alb_lcus))
            if 'pricingRecords' in alb_cost:
                pricing_records.extend(alb_cost['pricingRecords'])
                ec2Cost = ec2Cost + alb_cost['totalCost']



        #Calculate EC2 compute time for ALL instance types found (subscribed to ELB or not) - group by instance types
        all_instance_dict = {}
        all_instance_dict.update(ec2_instances)
        all_instance_types = get_instance_type_count(all_instance_dict)
        log.info("All instance types:{}".format(all_instance_types))

        #Calculate EC2 compute time cost
        #TODO: add support for all available OS
        for instance_type in all_instance_types:
            try:
                ec2_compute_cost = ec2pricing.calculate(data.Ec2PriceDimension(region=region, instanceType=instance_type, instanceHours=all_instance_types[instance_type]*HOURS_DICT[DEFAULT_FORECAST_PERIOD]))
                if 'pricingRecords' in ec2_compute_cost: pricing_records.extend(ec2_compute_cost['pricingRecords'])
                ec2Cost = ec2Cost + ec2_compute_cost['totalCost']
            except Exception as failure:
                log.error('Error processing %s: %s', instance_type, failure)

        #Get provisioned storage by volume type, and provisioned IOPS (if applicable)
        ebs_storage_dict, piops = get_storage_by_ebs_type(all_instance_dict)

        #Calculate EBS storagecost
        for k in ebs_storage_dict.keys():
            if k == 'io1': pricing_piops = piops
            else: pricing_piops = 0
            try:
                ebs_storage_cost = ec2pricing.calculate(data.Ec2PriceDimension(region=region, ebsVolumeType=k, ebsStorageGbMonth=ebs_storage_dict[k], pIops=pricing_piops))
                if 'pricingRecords' in ebs_storage_cost: pricing_records.extend(ebs_storage_cost['pricingRecords'])
                ec2Cost = ec2Cost + ebs_storage_cost['totalCost']
            except Exception as failure:
                log.error('Error processing ebs storage costs: %s', failure)


        #Get tagged RDS DB instances
        #db_instances = get_db_instances_by_tag(tagkey, tagvalue)
        db_instances = get_db_instances_by_tag(resource_manager.get_resource_ids(SERVICE_RDS, RESOURCE_RDS_DB_INSTANCE))
        if db_instances:
            log.info("Found the following tagged DB instances:{}".format(db_instances.keys()))
        else:
            log.info("Didn't find any tagged RDS DB instances")

        #Calculate RDS instance time for ALL instance types found - group by DB instance types
        all_db_instance_dict = {}
        all_db_instance_dict.update(db_instances)
        all_db_instance_types = get_db_instance_type_count(all_db_instance_dict)
        all_db_storage_types = get_db_storage_type_count(all_db_instance_dict)

        #TODO: add support for read replicas

        #Calculate RDS instance time cost
        rds_instance_cost = {}
        for db_instance_type in all_db_instance_types:
            try:
                dbInstanceClass = db_instance_type.split("|")[0]
                engine = db_instance_type.split("|")[1]
                licenseModel= db_instance_type.split("|")[2]
                multiAz= bool(int(db_instance_type.split("|")[3]))
                log.info("Calculating RDS DB Instance compute time")
                rds_instance_cost = rdspricing.calculate(data.RdsPriceDimension(region=region, dbInstanceClass=dbInstanceClass, multiAz=multiAz,
                                                engine=engine, licenseModel=licenseModel, instanceHours=all_db_instance_types[db_instance_type]*HOURS_DICT[DEFAULT_FORECAST_PERIOD]))

                if 'pricingRecords' in rds_instance_cost: pricing_records.extend(rds_instance_cost['pricingRecords'])
                rdsCost = rdsCost + rds_instance_cost['totalCost']
            except Exception as failure:
                log.error('Error processing RDS instance time costs: %s', failure)

        #Calculate RDS storage cost
        #TODO: add support for Aurora operations
        rds_storage_cost = {}
        for storage_key in all_db_storage_types.keys():
            try:
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
            except Exception as failure:
                log.error('Error processing RDS storage costs: %s', failure)

        #RDS Data Transfer - the Lambda function will assume all data transfer happens between RDS and EC2 instances

        #Lambda functions
        #TODO: add support for lambda function qualifiers
        #TODO: calculate data ingested into CloudWatch Logs
        lambdafunctions = resource_manager.get_resources(SERVICE_LAMBDA, RESOURCE_LAMBDA_FUNCTION)
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
              try:
                  #Note we're setting data transfer = 0, since we don't have a way to calculate it based on CW metrics alone
                  #TODO:call a single time and include a GB-s price dimension to the Lambda calculator
                  lambdapdim = data.LambdaPriceDimension(region=region, requestCount=executions*calculate_forecast_factor(),
                                                    avgDurationMs=avgduration, memoryMb=memory, dataTranferOutInternetGb=0,
                                                    dataTranferOutIntraRegionGb=0, dataTranferOutInterRegionGb=0, toRegion='')
                  lambda_func_cost = lambdapricing.calculate(lambdapdim)
                  if 'pricingRecords' in lambda_func_cost: pricing_records.extend(lambda_func_cost['pricingRecords'])
                  lambdaCost = lambdaCost + lambda_func_cost['totalCost']

              except Exception as failure:
                  log.error('Error processing Lambda costs: %s', failure)
          else:
              log.info("Skipping pricing calculation for function [{}] - qualifier [{}] due to lack of executions in [{}-minute] time window".format(fullname, qualifier, METRIC_WINDOW))


        #DynamoDB
        totalRead = 0
        totalWrite = 0
        ddbtables = resource_manager.get_resources(SERVICE_DYNAMODB, RESOURCE_DDB_TABLE)
        #Provisioned Capacity Units
        for t in ddbtables:
            read, write = get_ddb_capacity_units(t.id)
            log.info("Dynamo DB Provisioned Capacity Units - Table:{} Read:{} Write:{}".format(t.id, read, write))
            totalRead += read
            totalWrite += write
        #TODO: add support for storage
        if totalRead and totalWrite:
            ddbpdim = data.DynamoDBPriceDimension(region=region, readCapacityUnitHours=totalRead*HOURS_DICT[FORECAST_PERIOD_MONTHLY],
                                                                 writeCapacityUnitHours=totalWrite*HOURS_DICT[FORECAST_PERIOD_MONTHLY])
            ddbtable_cost = ddbpricing.calculate(ddbpdim)
            if 'pricingRecords' in ddbtable_cost: pricing_records.extend(ddbtable_cost['pricingRecords'])
            ddbCost = ddbCost + ddbtable_cost['totalCost']


        #Kinesis Streams
        streams = resource_manager.get_resources(SERVICE_KINESIS, RESOURCE_STREAM)
        totalShards = 0
        totalExtendedRetentionCount = 0
        totalPutPayloadUnits = 0
        for s in streams:
            log.info("Stream:[{}]".format(s.id))
            tmpShardCount, tmpExtendedRetentionCount = get_kinesis_stream_shards(s.id)
            totalShards += tmpShardCount
            totalExtendedRetentionCount += tmpExtendedRetentionCount

            totalPutPayloadUnits += calculate_kinesis_put_payload_units(start, end, s.id)

        if totalShards:
            kinesispdim = data.KinesisPriceDimension(region=region,
                                                     shardHours=totalShards*HOURS_DICT[FORECAST_PERIOD_MONTHLY],
                                                     extendedDataRetentionHours=totalExtendedRetentionCount*HOURS_DICT[FORECAST_PERIOD_MONTHLY],
                                                     putPayloadUnits=totalPutPayloadUnits*calculate_forecast_factor())
            stream_cost = kinesispricing.calculate(kinesispdim)
            if 'pricingRecords' in stream_cost: pricing_records.extend(stream_cost['pricingRecords'])

            kinesisCost = kinesisCost + stream_cost['totalCost']




        #Do this after all calculations for all supported services have concluded
        totalCost = ec2Cost + rdsCost + lambdaCost + ddbCost + kinesisCost
        result['pricingRecords'] = pricing_records
        result['totalCost'] = round(totalCost,2)
        result['forecastPeriod']=DEFAULT_FORECAST_PERIOD
        result['currency'] = CW_METRIC_DIMENSION_CURRENCY_USD

        #Publish metrics to CloudWatch using the default namespace

        if tagkey:
          put_cw_metric_data(end, ec2Cost, CW_METRIC_DIMENSION_SERVICE_NAME_EC2, tagkey, tagvalue)
          put_cw_metric_data(end, rdsCost, CW_METRIC_DIMENSION_SERVICE_NAME_RDS, tagkey, tagvalue)
          put_cw_metric_data(end, lambdaCost, CW_METRIC_DIMENSION_SERVICE_NAME_LAMBDA, tagkey, tagvalue)
          put_cw_metric_data(end, ddbCost, CW_METRIC_DIMENSION_SERVICE_NAME_DYNAMODB, tagkey, tagvalue)
          put_cw_metric_data(end, kinesisCost, CW_METRIC_DIMENSION_SERVICE_NAME_KINESIS, tagkey, tagvalue)
          put_cw_metric_data(end, totalCost, CW_METRIC_DIMENSION_SERVICE_NAME_TOTAL, tagkey, tagvalue)



        log.info("Estimated monthly cost for resources tagged with key={},value={} : [{}]".format(tagkey, tagvalue, json.dumps(result,sort_keys=False,indent=4)))

    except NoDataFoundError as ndf:
        log.error ("NoDataFoundError [{}]".format(ndf))

    except Exception as e:
        traceback.print_exc()
        log.error("Exception message:["+str(e)+"]")


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

"""
For each ALB, get the value for the ConsumedLCUs metric
"""


def calculate_alb_lcus(start, end, albs):
    result = 0

    for a in albs:
        log.info("Getting ConsumedLCUs for ALB: [{}]".format(a))
        metricsLcus = cwclient.get_metric_statistics(
            Namespace='AWS/ApplicationELB',
            MetricName='ConsumedLCUs',
            Dimensions=[{'Name': 'LoadBalancer','Value': "app/{}".format(a)}],
            StartTime=start,
            EndTime=end,
            Period=60*METRIC_WINDOW,
            Statistics = ['Sum']
        )
        for datapoint in metricsLcus['Datapoints']:
            result += datapoint.get('Sum',0)

    log.info ("Total ConsumedLCUs consumed by ALBs in time window of ["+str(METRIC_WINDOW)+"] minutes :["+str(result)+"]")

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


def get_ddb_capacity_units(tablename):
    read = 0
    write = 0
    try:
        r = ddbclient.describe_table(TableName=tablename)
        if 'Table' in r:
            read = r['Table']['ProvisionedThroughput']['ReadCapacityUnits']
            write = r['Table']['ProvisionedThroughput']['WriteCapacityUnits']
        return read, write

    except Exception as e:
        log.error("{}".format(e))


def get_kinesis_stream_shards(streamName):
    shardCount = 0
    extendedRetentionCount = 0
    try:
        #TODO: add support for streams with >100 shards
        #TODO: add support for detailed metrics
        response = kinesisclient.describe_stream(StreamName=streamName)
        shardCount = len(response['StreamDescription']['Shards'])
        if response['StreamDescription']['RetentionPeriodHours'] > 24:
            extendedRetentionCount = shardCount

    except Exception as e:
        log.error("{}".format(e))

    return shardCount, extendedRetentionCount

"""
This function calculates an approximation of PUT payload units, based on CloudWatch metrics.
Unfortunately, there is no direct CloudWatch metric that returns the PUT Payload Units for a stream.
https://aws.amazon.com/kinesis/streams/pricing/
PUT Payload Units are calculated in 25KB chunks and CloudWatch metrics return the number of records inserted
as well as the total bytes entering the stream. There is no accurate way to calculate the number of
25KB chunks going into the stream.

"""
def calculate_kinesis_put_payload_units(start, end, streamName):
    totalRecords = 0
    totalBytesAvg = 0
    totalPutPayloadUnits = 0
    chunkCount = 0 #Kinesis charges for PUT Payload Units in chunks of 25KB


    try:
        incomingRecords = cwclient.get_metric_statistics(
                Namespace='AWS/Kinesis',
                MetricName='IncomingRecords',
                Dimensions=[{'Name': 'StreamName','Value': streamName}],
                StartTime=start,
                EndTime=end,
                Period=60*METRIC_WINDOW,
                Statistics = ['Sum']
            )

        for datapoint in incomingRecords['Datapoints']:
          if 'Sum' in datapoint: totalRecords = totalRecords + datapoint['Sum']

        incomingBytes = cwclient.get_metric_statistics(
                Namespace='AWS/Kinesis',
                MetricName='IncomingBytes',
                Dimensions=[{'Name': 'StreamName','Value': streamName}],
                StartTime=start,
                EndTime=end,
                Period=60*METRIC_WINDOW,
                Statistics = ['Average']
            )

        for datapoint in incomingBytes['Datapoints']:
          if 'Average' in datapoint:
              chunkCount += int(math.ceil(datapoint['Average']/25000))

        bytesDatapoints = len(incomingBytes['Datapoints'])
        if not bytesDatapoints: bytesDatapoints = 1 #avoid zerodiv
        totalPutPayloadUnits = totalRecords * chunkCount/bytesDatapoints
        log.info("get_kinesis_stream_puts - incomingRecords:[{}] - chunkAvg:[{}] - totalPutPayloadUnits:[{}]".format(totalRecords, chunkCount/bytesDatapoints, totalPutPayloadUnits))

    except Exception as e:
        log.error("{}".format(e))


    return totalPutPayloadUnits


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
    global ddbclient
    global kinesisclient
    global cwclient
    global tagsclient
    global region
    global awsaccount


    arn = context.invoked_function_arn
    region = arn.split(":")[3] #ARN format is arn:aws:lambda:us-east-1:xxx:xxxx
    awsaccount = arn.split(":")[4]
    ec2client = boto3.client('ec2',region)
    rdsclient = boto3.client('rds',region)
    elbclient = boto3.client('elb',region) #classic load balancers
    elbclientv2 = boto3.client('elbv2',region) #application and network load balancers
    lambdaclient = boto3.client('lambda',region)
    ddbclient = boto3.client('dynamodb',region)
    kinesisclient = boto3.client('kinesis',region)
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
                    #log.info("Tagged resource:{}".format(res.__dict__))

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
        for service in (SERVICE_EC2, SERVICE_ELB, SERVICE_DYNAMODB, SERVICE_KINESIS):
            for type in (RESOURCE_ALB, RESOURCE_NLB, RESOURCE_ELB):
                if ':'+service+':' in arn and ':'+type+'/' in arn:
                    resourceId = arn.split(':'+type+'/')[1]
                    return self.Resource(service, type, resourceId, arn)

            for type in (RESOURCE_EC2_INSTANCE,RESOURCE_EBS_VOLUME,RESOURCE_EBS_SNAPSHOT,RESOURCE_DDB_TABLE, RESOURCE_STREAM):
                if ':'+service+':' in arn and ':'+type+'/' in arn:
                    resourceId = arn.split(':'+type+'/')[1]
                    return self.Resource(service, type, resourceId, arn)
        for service in (SERVICE_RDS, SERVICE_LAMBDA):
            for type in (RESOURCE_RDS_DB_INSTANCE, RESOURCE_LAMBDA_FUNCTION):
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
