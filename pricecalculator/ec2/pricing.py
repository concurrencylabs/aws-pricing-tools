import json
import logging
import os, sys
from ..common import consts, phelper
from ..common.errors import ValidationError
from ..common.data import ElbPriceDimension, PricingResult, PricingRecord

log = logging.getLogger()


def calculate(**kwargs):
  log.info("Calculating EC2 pricing with the following inputs: {}".format(str(kwargs)))

  region = ''
  if 'region' in kwargs: region = kwargs['region']

  instanceType = ''
  if 'instanceType' in kwargs: instanceType = kwargs['instanceType']

  instanceHours = 0
  if 'instanceHours' in kwargs: instanceHours = kwargs['instanceHours']

  operatingSystem = consts.SCRIPT_OPERATING_SYSTEM_LINUX
  if 'operatingSystem' in kwargs: operatingSystem = kwargs['operatingSystem']

  dataOutInternetGbMonth = 0
  if 'dataOutInternetGbMonth' in kwargs: dataOutInternetGbMonth = kwargs['dataOutInternetGbMonth']

  pIops = 0
  if 'pIops' in kwargs: pIops = kwargs['pIops']

  ebsVolumeType = ''
  if 'ebsVolumeType' in kwargs: ebsVolumeType = kwargs['ebsVolumeType']

  ebsStorageGbMonth = 0
  if 'ebsStorageGbMonth' in kwargs: ebsStorageGbMonth = kwargs['ebsStorageGbMonth']

  ebsSnapshotGbMonth = 0
  if 'ebsSnapshotGbMonth' in kwargs: ebsSnapshotGbMonth = kwargs['ebsSnapshotGbMonth']

  elbHours = 0
  if 'elbHours' in kwargs: elbHours = kwargs['elbHours']
  
  elbDataProcessedGb = 0
  if 'elbDataProcessedGb' in kwargs: elbDataProcessedGb = kwargs['elbDataProcessedGb']

  intraRegionDataTransferGb = 0
  if 'intraRegionDataTransferGb' in kwargs: intraRegionDataTransferGb = kwargs['intraRegionDataTransferGb']

  storageMedia = ''
  if ebsVolumeType in consts.EBS_VOLUME_TYPES_MAP: storageMedia = consts.EBS_VOLUME_TYPES_MAP[ebsVolumeType]['storageMedia']

  volumeType = ''
  if ebsVolumeType in consts.EBS_VOLUME_TYPES_MAP: volumeType = consts.EBS_VOLUME_TYPES_MAP[ebsVolumeType]['volumeType']

  validate(region, instanceType, operatingSystem, dataOutInternetGbMonth, ebsVolumeType)

  __location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
  index_file = open(os.path.join(__location__, 'index.json')).read();
  price_data = json.loads(index_file)
  awsPriceListApiVersion = price_data['version']

  #usage_type = phelper.get_distinct_product_attributes(price_data, 'usagetype', **kwargs)

  cost = 0
  pricing_records = []
  skus = phelper.get_skus(price_data, region=region)

  #print("size of price_data:["+str(sys.getsizeof(price_data))+"] - size of skus:["+ str(sys.getsizeof(skus))+"]")

  #TODO: Optimize the way we access skus in json file. We are iterating over a large number of SKUs. In the future it would be good to create a DDB table for SKUs
  for sku in skus:
    service = consts.SERVICE_EC2

    sku_data = price_data['products'][sku]
    #TODO: add support for Reserved and Spot
    term_data = phelper.get_terms(price_data, [sku], type='OnDemand')
    pd = phelper.get_price_dimensions(term_data)
    #print("sku_data:"+json.dumps(sku_data,sort_keys=True,indent=4, separators=(',', ': ')))
    #print("term_data:"+json.dumps(term_data,sort_keys=True,indent=4, separators=(',', ': ')))
    #print("price_dimensions:"+json.dumps(pd,sort_keys=True,indent=4, separators=(',', ': ')))

    for p in pd:
      amt = 0
      usageUnits = 0
      billableBand = 0
      pricePerUnit = 0

      pricePerUnit = float(p['pricePerUnit']['USD'])
      #Compute Instance
      if sku_data['productFamily'] == consts.PRODUCT_FAMILY_COMPUTE_INSTANCE:
        usageUnits = instanceHours
        if sku_data['attributes']['instanceType'] == instanceType and sku_data['attributes']['operatingSystem'] == consts.EC2_OPERATING_SYSTEMS_MAP[operatingSystem]:
          amt = pricePerUnit * float(usageUnits)
          #print("Calculating EC2 hours: amt["+str(amt)+"] - pricePerUnit:["+str(pricePerUnit)+"]")

      #Data Transfer
      if sku_data['productFamily'] == consts.PRODUCT_FAMILY_DATA_TRANSFER:
        billableBand = 0
        #To internet            
        if dataOutInternetGbMonth and sku_data['attributes']['servicecode'] == consts.SERVICE_CODE_AWS_DATA_TRANSFER and sku_data['attributes']['toLocation'] == 'External' and sku_data['attributes']['transferType'] == 'AWS Outbound':
          billableBand = phelper.getBillableBand(p, dataOutInternetGbMonth)
          amt = pricePerUnit * billableBand

        #Intra-regional data transfer - in/out/between EC2 AZs or using IPs or ELB
        if intraRegionDataTransferGb and sku_data['attributes']['servicecode'] == consts.SERVICE_CODE_AWS_DATA_TRANSFER and sku_data['attributes']['transferType'] == 'IntraRegion':
          usageUnits = intraRegionDataTransferGb
          amt = pricePerUnit * usageUnits

      #EIP
        
      #EBS Storage
      if ebsStorageGbMonth and sku_data['productFamily'] == consts.PRODUCT_FAMILY_STORAGE:
        service = consts.SERVICE_EBS
        usageUnits = ebsStorageGbMonth
        #print("will calculate EBS - storageMedia:["+storageMedia+"] - volumeType:["+volumeType+"]")
        if sku_data['attributes']['storageMedia'] == storageMedia and sku_data['attributes']['volumeType'] == volumeType:
          amt = pricePerUnit * usageUnits

      #System Operation (for IOPS)
      if sku_data['productFamily'] == consts.PRODUCT_FAMILY_SYSTEM_OPERATION:
        service = consts.SERVICE_EBS
        usageUnits = pIops
        if sku_data['attributes']['group'] == 'EBS IOPS' :
          #pricePerUnit = float(p['pricePerUnit']['USD'])
          amt = pricePerUnit * float(usageUnits)

      #Storage Snapshot
      if sku_data['productFamily'] == consts.PRODUCT_FAMILY_SNAPSHOT:
        service = consts.SERVICE_EBS
        if 'EBS:SnapshotUsage' in sku_data['attributes']['usagetype']: usageUnits = ebsSnapshotGbMonth
        amt = pricePerUnit * usageUnits



      #Load Balancer
      if sku_data['productFamily'] == consts.PRODUCT_FAMILY_LOAD_BALANCER:
        service = consts.SERVICE_ELB
        if 'LoadBalancerUsage' in sku_data['attributes']['usagetype']: usageUnits = elbHours
        if 'DataProcessing-Bytes' in sku_data['attributes']['usagetype']: usageUnits = elbDataProcessedGb
        amt = pricePerUnit * float(usageUnits)

      #Dedicated Host
    

      #NAT Gateway
      
      #Fee
      if sku_data['productFamily'] == consts.PRODUCT_FAMILY_FEE:
        pass

      if amt > 0:
        cost = cost + amt
        if billableBand > 0: usageUnits = billableBand
        pricing_record = PricingRecord(service,round(amt,4),p['description'],pricePerUnit,usageUnits,p['rateCode'])
        pricing_records.append(vars(pricing_record))

  pricing_result = PricingResult(awsPriceListApiVersion, region, cost, pricing_records)
  log.debug(json.dumps(vars(pricing_result),sort_keys=False,indent=4))
  return pricing_result.__dict__



def validate(region, instanceType, operatingSystem, dataOutInternetGbMonth, ebsVolumeType):
  validation_ok = True
  validation_message = ""

  if instanceType and instanceType not in consts.SUPPORTED_INSTANCE_TYPES:
    validation_message = "instance-type must be one of the following values:"+str(consts.SUPPORTED_INSTANCE_TYPES)
    validation_ok = False
  if region not in consts.SUPPORTED_REGIONS:
    validation_message = "region must be one of the following values:"+str(consts.SUPPORTED_REGIONS)
    validation_ok = False
  if operatingSystem and operatingSystem not in consts.SUPPORTED_EC2_OPERATING_SYSTEMS:
    validation_message = "operating-system must be one of the following values:"+str(consts.SUPPORTED_EC2_OPERATING_SYSTEMS)
    validation_ok = False
  if ebsVolumeType and ebsVolumeType not in consts.SUPPORTED_EBS_VOLUME_TYPES:
    validation_message = "ebs-volume-type must be one of the following values:"+str(consts.SUPPORTED_EBS_VOLUME_TYPES)
    validation_ok = False
  #TODO: add validation for max number of IOPS
  #TODO: add validation for negative numbers

  if not validation_ok:
      raise ValidationError(validation_message)

  return

