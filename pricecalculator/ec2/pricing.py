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

  #TODO:remove the Month
  dataOutInternetGbMonth = 0
  if 'dataOutInternetGbMonth' in kwargs: dataOutInternetGbMonth = kwargs['dataOutInternetGbMonth']

  interRegionDataTransferGb = 0
  if 'interRegionDataTransferGb' in kwargs: interRegionDataTransferGb = kwargs['interRegionDataTransferGb']

  toRegion = ''
  if 'toRegion' in kwargs: toRegion = kwargs['toRegion']

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


  #Assign default values
  if not operatingSystem:
    operatingSystem = consts.SCRIPT_OPERATING_SYSTEM_LINUX
  if not volumeType:
    volumeType = consts.SCRIPT_EBS_VOLUME_TYPE_GP2
  #TODO: Add support for shared and dedicated tenancies
  tenancy = consts.EC2_TENANCY_SHARED


  validate(region, instanceType, operatingSystem, dataOutInternetGbMonth, ebsVolumeType)

  __location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
  index_file = open(os.path.join(__location__, 'index.json')).read();
  price_data = json.loads(index_file)
  awsPriceListApiVersion = price_data['version']

  #usage_type = phelper.get_distinct_product_attributes(price_data, 'usagetype', **kwargs)

  cost = 0
  pricing_records = []
  skus = phelper.get_skus(price_data, region=region)

  #TODO: Optimize the way we access skus in json file. We are iterating over a large number of SKUs. In the future it would be good to create a DDB table for SKUs
  #TODO: Exit when all input parameters have been evaluated - avoid iterating unnecessarily through the SKUs
  for sku in skus:
    service = consts.SERVICE_EC2

    sku_data = price_data['products'][sku]
    #TODO: add support for Reserved and Spot
    term_data = phelper.get_terms(price_data, [sku], type='OnDemand')
    pd = phelper.get_price_dimensions(term_data)

    for p in pd:
      amt = 0
      usageUnits = 0
      billableBand = 0
      pricePerUnit = 0

      pricePerUnit = float(p['pricePerUnit']['USD'])
      #Compute Instance
      if sku_data['productFamily'] == consts.PRODUCT_FAMILY_COMPUTE_INSTANCE:
        usageUnits = instanceHours
        if sku_data['attributes']['instanceType'] == instanceType and sku_data['attributes']['operatingSystem'] == consts.EC2_OPERATING_SYSTEMS_MAP[operatingSystem]\
                and sku_data['attributes']['tenancy'] == consts.EC2_TENANCY_SHARED:
          amt = pricePerUnit * float(usageUnits)

      #Data Transfer
      if sku_data['productFamily'] == consts.PRODUCT_FAMILY_DATA_TRANSFER:
        billableBand = 0
        #To internet            
        if dataOutInternetGbMonth and sku_data['attributes']['servicecode'] == consts.SERVICE_CODE_AWS_DATA_TRANSFER and sku_data['attributes']['toLocation'] == 'External' and sku_data['attributes']['transferType'] == 'AWS Outbound':
          billableBand = phelper.getBillableBand(p, dataOutInternetGbMonth)
          amt = pricePerUnit * billableBand

        #Intra-regional data transfer - in/out/between EC2 AZs or using EIPs or ELB
        if intraRegionDataTransferGb and phelper.is_data_transfer_intraregional(sku_data):
          usageUnits = intraRegionDataTransferGb
          amt = pricePerUnit * usageUnits

        #Inter-regional data transfer - out to other AWS regions
        if interRegionDataTransferGb and phelper.is_data_transfer_interregional(sku_data, toRegion):
          usageUnits = interRegionDataTransferGb
          amt = pricePerUnit * usageUnits



      #EIP
        
      #EBS Storage
      if ebsStorageGbMonth and sku_data['productFamily'] == consts.PRODUCT_FAMILY_STORAGE:
        service = consts.SERVICE_EBS
        usageUnits = ebsStorageGbMonth
        if sku_data['attributes']['storageMedia'] == storageMedia and sku_data['attributes']['volumeType'] == volumeType:
          amt = pricePerUnit * float(usageUnits)

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
        amt = pricePerUnit * float(usageUnits)



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
  #TODO: add validation for inter-regional data transfer: to-region is mandatory

  if not validation_ok:
      raise ValidationError(validation_message)

  return

