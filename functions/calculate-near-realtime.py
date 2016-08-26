from __future__ import print_function

import datetime
import json
import logging
import boto3
import pricecalculator.ec2.pricing as ec2pricing

log = logging.getLogger()
log.setLevel(logging.INFO)

ec2client = None
elbclient = None
cwclient = None


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
CW_METRIC_DIMENSION_CURRENCY_USD = 'USD'


#_/_/_/_/_/_/ default values - end _/_/_/_/_/_/



"""
Limitations (features not yet available):
    - Calculates all NetworkOut metrics as 'out to the internet', since there is no way to know in near real-time
      with CloudWath metrics the bytes destination. This would only be possible using VPC Flow Logs, which are not
      near real-time.
"""

def handler(event, context):

    log.info("Received event {}".format(json.dumps(event)))

    init_clients(context)

    result = {}
    pricing_records = []
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

    start, end = calculate_time_range()

    #Get ELB(s) with the tags we're looking for.
    elbnames = find_elbs(tagkey, tagvalue)
    if elbnames:
        log.info("Found ELBs:{}".format(elbnames))
        elb_hours = len(elbnames)*HOURS_DICT[DEFAULT_FORECAST_PERIOD]

    #Get all instances registered to each of the found ELBs
    elb_instances = get_elb_instances(elbnames)
    if elb_instances:
      log.info("Found ELB-registered EC2 instances:{}".format(elb_instances.keys()))
    else:
      log.info("Didn't find any ELB-registered EC2 instances")

    elb_data_processed_gb = calculate_elb_data_processed(start, end, elb_instances)*calculate_forecast_factor() / (10**9)

    #Get EC2 instances with the tag
    non_elb_instances = get_non_elb_instances_by_tag(tagkey, tagvalue, elb_instances)
    if non_elb_instances:
        log.info("Non ELB-registered EC2 instances:{}".format(non_elb_instances.keys()))
    else:
        log.info("Didn't find any standalone EC2 instances")


    #Calculate ELB cost
    elb_cost = ec2pricing.calculate(region=region, elbHours=elb_hours, elbDataProcessedGb=elb_data_processed_gb)
    if 'pricingRecords' in elb_cost: pricing_records.extend(elb_cost['pricingRecords'])
    totalCost = totalCost + elb_cost['totalCost']


    #Calculate EC2 compute time for ALL instance types found (subscribed to ELB or not) - group by instance types
    all_instance_dict = {}
    all_instance_dict.update(elb_instances)
    all_instance_dict.update(non_elb_instances)
    all_instance_types = get_instance_type_count(all_instance_dict)
    log.info("All instance types:{}".format(all_instance_types))


    #Calculate EC2 compute time cost
    for instance_type in all_instance_types:
        ec2_cost = ec2pricing.calculate(region=region, instanceType=instance_type, instanceHours=all_instance_types[instance_type]*HOURS_DICT[DEFAULT_FORECAST_PERIOD])
        if 'pricingRecords' in ec2_cost: pricing_records.extend(ec2_cost['pricingRecords'])
        totalCost = totalCost + ec2_cost['totalCost']

    #Get provisioned storage by volume type, and provisioned IOPS (if applicable)
    ebs_storage_dict, piops = get_storage_by_ebs_type(all_instance_dict)

    #Calculate EBS storagecost
    for k in ebs_storage_dict.keys():
        if k == 'io1': pricing_piops = piops
        else: pricing_piops = 0
        ebs_storage_cost = ec2pricing.calculate(region=region, ebsVolumeType=k, ebsStorageGbMonth=ebs_storage_dict[k], pIops=pricing_piops)
        if 'pricingRecords' in ebs_storage_cost: pricing_records.extend(ebs_storage_cost['pricingRecords'])
        totalCost = totalCost + ebs_storage_cost['totalCost']

    #Get total snapshot storage
    snapshot_gb_month = get_total_snapshot_storage(tagkey, tagvalue)
    ebs_snapshot_cost = ec2pricing.calculate(region=region, ebsSnapshotGbMonth=snapshot_gb_month)
    if 'pricingRecords' in ebs_snapshot_cost: pricing_records.extend(ebs_snapshot_cost['pricingRecords'])
    totalCost = totalCost + ebs_snapshot_cost['totalCost']

    result['pricingRecords'] = pricing_records
    result['totalCost'] = round(totalCost,2)
    result['forecastPeriod']=DEFAULT_FORECAST_PERIOD
    result['currency'] = CW_METRIC_DIMENSION_CURRENCY_USD


    #Publish metrics to CloudWatch using the default namespace
    response = cwclient.put_metric_data(
        Namespace=CW_NAMESPACE,
        MetricData=[
            {
                'MetricName': CW_METRIC_NAME_ESTIMATEDCHARGES,
                'Dimensions': [{'Name': CW_METRIC_DIMENSION_SERVICE_NAME,'Value': CW_METRIC_DIMENSION_SERVICE_NAME_EC2},
                               {'Name': CW_METRIC_DIMENSION_PERIOD,'Value': DEFAULT_FORECAST_PERIOD},
                               {'Name': CW_METRIC_DIMENSION_CURRENCY,'Value': CW_METRIC_DIMENSION_CURRENCY_USD},
                               {'Name': CW_METRIC_DIMENSION_TAG,'Value': tagkey+'='+tagvalue}
                ],
                'Timestamp': end,
                'Value': result['totalCost'],
                'Unit': 'Count'
            }
        ]
    )

    log.info (json.dumps(result,sort_keys=False,indent=4))

    return result

#TODO: log the actual AWS resources that are found for the price calculation
#TODO: add support for detailed metrics fee
#TODO: add support for EBS optimized
#TODO: add support for EIP
#TODO: add support for EC2 operating systems other than Linux
#TODO: add support for ALL instance types
#TODO: calculate monthly hours based on the current month, instead of assuming 720
#TODO: add support for dynamic forecast period (1 hour, 1 day, 1 month, etc.)
#TODO: add support for Spot and Reserved. Function only supports On-demand instances at the time




def find_elbs(tagkey, tagvalue):
    result = []
    elbs = elbclient.describe_load_balancers(LoadBalancerNames=[])
    all_elb_names = []
    if 'LoadBalancerDescriptions' in elbs:
        for e in elbs['LoadBalancerDescriptions']:
            all_elb_names.append(e['LoadBalancerName'])

    tag_desc = elbclient.describe_tags(LoadBalancerNames=all_elb_names)
    for tg in tag_desc['TagDescriptions']:
        tags = tg['Tags']
        for t in tags:
            if t['Key']==tagkey and t['Value']==tagvalue:
                result.append(tg['LoadBalancerName'])
    return result


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

    #print("Looking for the following ELB instances:["+str(instance_ids)+"]")
    if instance_ids:
        response = ec2client.describe_instances(InstanceIds=instance_ids)
        if 'Reservations' in response:
            for r in response['Reservations']:
                if 'Instances' in r:
                    for i in r['Instances']:
                        result[i['InstanceId']]=i

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

    print("total snapshot size:["+str(result)+"]")
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


def calculate_time_range():
    start = datetime.datetime.utcnow() + datetime.timedelta(minutes=-METRIC_DELAY)
    end = start + datetime.timedelta(minutes=METRIC_WINDOW)
    log.info("start:["+str(start)+"] - end:["+str(end)+"]")
    return start, end



def calculate_forecast_factor():
    result = (60 / METRIC_WINDOW ) * HOURS_DICT[DEFAULT_FORECAST_PERIOD]
    print("forecast factor:["+str(result)+"]")
    return result



def get_ec2_instances(registered, all):
    result = []
    for a in all:
        if a not in registered: result.append(a)
    return result


def init_clients(context):
    global ec2client
    global elbclient
    global cwclient
    global region

    arn = context.invoked_function_arn
    region = arn.split(":")[3] #ARN format is arn:aws:lambda:us-east-1:xxx:xxxx
    ec2client = boto3.client('ec2',region)
    elbclient = boto3.client('elb',region)
    cwclient = boto3.client('cloudwatch', region)



