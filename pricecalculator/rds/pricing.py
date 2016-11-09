import json
import logging
import os, sys
from ..common import consts, phelper
from ..common.errors import ValidationError
from ..common.data import PricingResult, PricingRecord

log = logging.getLogger()


def calculate(**kwargs):
  log.info("Calculating RDS pricing with the following inputs: {}".format(str(kwargs)))

  region = ''
  if 'region' in kwargs: region = kwargs['region']

  dbInstanceClass = ''
  if 'dbInstanceClass' in kwargs: dbInstanceClass = kwargs['dbInstanceClass']

  engine = ''
  if 'engine' in kwargs: engine = kwargs['engine']

  licenseModel = ''
  if 'licenseModel' in kwargs: licenseModel = kwargs['licenseModel']
  if engine in (consts.SCRIPT_RDS_DATABASE_ENGINE_MYSQL,consts.SCRIPT_RDS_DATABASE_ENGINE_POSTGRESQL, consts.SCRIPT_RDS_DATABASE_ENGINE_AURORA):
      licenseModel = consts.SCRIPT_RDS_LICENSE_MODEL_PUBLIC


  instanceHours = 0
  if 'instanceHours' in kwargs: instanceHours = kwargs['instanceHours']

  multiAz = False
  if 'multiAz' in kwargs:multiAz = kwargs['multiAz']

  internetDataTransferOutGb = 0
  if 'internetDataTransferOutGb' in kwargs: internetDataTransferOutGb = kwargs['internetDataTransferOutGb']

  interRegionDataTransferGb = 0
  if 'interRegionDataTransferGb' in kwargs: interRegionDataTransferGb = kwargs['interRegionDataTransferGb']


  #Commenting out for now, until Price List API supports storage price dimensions in its data set.
  """
  storageGbMonth = 0
  if 'storageGbMonth' in kwargs: storageGbMonth = kwargs['storageGbMonth']

  storageType = ''
  if 'storageType' in kwargs: storageType = kwargs['storageType']


  ioRate = 0
  if 'ioRate' in kwargs: iorate = kwargs['ioRate']

  backupStorageGbMonth = 0
  if 'backupStorageGbMonth' in kwargs: backupStorageGbMonth = kwargs['backupStorageGbMonth']
  """

  validate(region, dbInstanceClass, engine, licenseModel, instanceHours, multiAz, internetDataTransferOutGb, interRegionDataTransferGb)

  skuEngine = consts.RDS_ENGINE_MAP[engine]['engine']
  skuEngineEdition = consts.RDS_ENGINE_MAP[engine]['edition']
  skuLicenseModel = consts.RDS_LICENSE_MODEL_MAP[licenseModel]



  __location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
  index_file = open(os.path.join(__location__, 'index.json')).read();
  price_data = json.loads(index_file)
  awsPriceListApiVersion = price_data['version']

  cost = 0
  pricing_records = []
  skus = phelper.get_skus(price_data, region=region)
  #print("SKUs to evaluate:["+str(len(skus))+"]")
  #print("size of price_data:["+str(sys.getsizeof(price_data))+"] - size of skus:["+ str(sys.getsizeof(skus))+"]")


  for sku in skus:
    service = consts.SERVICE_RDS

    sku_data = price_data['products'][sku]
    #TODO: add support for Reserved
    term_data = phelper.get_terms(price_data, [sku], type='OnDemand')
    pd = phelper.get_price_dimensions(term_data)

    for p in pd:
      amt = 0
      usageUnits = 0
      billableBand = 0
      pricePerUnit = float(p['pricePerUnit']['USD'])
      #DB Instance
      if sku_data['productFamily'] == consts.PRODUCT_FAMILY_DATABASE_INSTANCE:
        usageUnits = instanceHours
        dbMatch = False
        if 'databaseEdition' in sku_data['attributes']:
          if dbInstanceClass == sku_data['attributes']['instanceType'] \
                and skuEngine == sku_data['attributes']['databaseEngine'] \
                and skuEngineEdition == sku_data['attributes']['databaseEdition']\
                and skuLicenseModel == sku_data['attributes']['licenseModel']:
            dbMatch = True
        else:
          if dbInstanceClass == sku_data['attributes']['instanceType'] \
                and skuEngine == sku_data['attributes']['databaseEngine'] \
                and skuLicenseModel == sku_data['attributes']['licenseModel']:
            dbMatch = True

        if dbMatch:
          #Multi/Single AZ
          if (multiAz and sku_data['attributes']['deploymentOption'] == consts.RDS_DEPLOYMENT_OPTION_MULTI_AZ)\
              or (not multiAz and sku_data['attributes']['deploymentOption'] == consts.RDS_DEPLOYMENT_OPTION_SINGLE_AZ):

            amt = pricePerUnit * float(usageUnits)

      #Reserved

      #Data Transfer
      """
      if sku_data['productFamily'] == consts.PRODUCT_FAMILY_DATA_TRANSFER:
        billableBand = 0
        #To internet            
        if internetDataTransferOutGb and sku_data['attributes']['servicecode'] == consts.SERVICE_CODE_AWS_DATA_TRANSFER and sku_data['attributes']['toLocation'] == 'External' and sku_data['attributes']['transferType'] == 'AWS Outbound':
          billableBand = phelper.getBillableBand(p, internetDataTransferOutGb)
          amt = pricePerUnit * billableBand

        #Inter-regional data transfer - to other AWS regions
        if interRegionDataTransferGb and sku_data['attributes']['servicecode'] == consts.SERVICE_CODE_AWS_DATA_TRANSFER and sku_data['attributes']['transferType'] == 'InterRegion Outbound':
          usageUnits = interRegionDataTransferGb
          amt = pricePerUnit * usageUnits
      """


        
      #Storage (magnetic, SSD, PIOPS)
      """
      if storageGbMonth and sku_data['productFamily'] == consts.PRODUCT_FAMILY_STORAGE:
        service = consts.SERVICE_EBS
        usageUnits = ebsStorageGbMonth
        #print("will calculate EBS - storageMedia:["+storageMedia+"] - volumeType:["+volumeType+"]")
        if sku_data['attributes']['storageMedia'] == storageMedia and sku_data['attributes']['volumeType'] == volumeType:
          amt = pricePerUnit * usageUnits
      """

      """
      #System Operation (for IOPS)
      if sku_data['productFamily'] == consts.PRODUCT_FAMILY_SYSTEM_OPERATION:
        service = consts.SERVICE_EBS
        usageUnits = pIops
        if sku_data['attributes']['group'] == 'EBS IOPS' :
          #pricePerUnit = float(p['pricePerUnit']['USD'])
          amt = pricePerUnit * float(usageUnits)
      """


      #Backup Storage
      """
      if sku_data['productFamily'] == consts.PRODUCT_FAMILY_SNAPSHOT:
        service = consts.SERVICE_EBS
        if 'EBS:SnapshotUsage' in sku_data['attributes']['usagetype']: usageUnits = ebsSnapshotGbMonth
        amt = pricePerUnit * usageUnits
      """

      if amt > 0:
        cost = cost + amt
        if billableBand > 0: usageUnits = billableBand
        pricing_record = PricingRecord(service,round(amt,4),p['description'],pricePerUnit,usageUnits,p['rateCode'])
        pricing_records.append(vars(pricing_record))

  pricing_result = PricingResult(awsPriceListApiVersion, region, cost, pricing_records)
  log.debug(json.dumps(vars(pricing_result),sort_keys=False,indent=4))
  return pricing_result.__dict__



def validate(region, dbInstanceClass, engine, licenseModel, instanceHours, multiAz, internetDataTransferOutGb, interRegionDataTransferGb):
  validation_ok = True
  validation_message = ""
  valid_engine = True

  if dbInstanceClass and dbInstanceClass not in consts.SUPPORTED_RDS_INSTANCE_CLASSES:
    validation_message = "\n" + "db-instance-class must be one of the following values:"+str(consts.SUPPORTED_RDS_INSTANCE_CLASSES)
    validation_ok = False
  if region not in consts.SUPPORTED_REGIONS:
    validation_message += "\n" + "region must be one of the following values:"+str(consts.SUPPORTED_REGIONS)
    validation_ok = False
  if engine not in consts.RDS_SUPPORTED_DB_ENGINES:
    validation_message += "\n" + "engine must be one of the following values:"+str(consts.RDS_SUPPORTED_DB_ENGINES)
    valid_engine  = False
    validation_ok = False
  if valid_engine and engine not in (consts.SCRIPT_RDS_DATABASE_ENGINE_MYSQL,consts.SCRIPT_RDS_DATABASE_ENGINE_POSTGRESQL, consts.SCRIPT_RDS_DATABASE_ENGINE_AURORA):
    if licenseModel not in (consts.RDS_SUPPORTED_LICENSE_MODELS):
      validation_message += "\n" + "license-model must be one of the following values:"+str(consts.RDS_SUPPORTED_LICENSE_MODELS)
      validation_ok = False

  #TODO: add validation for negative numbers

  if not validation_ok:
      raise ValidationError(validation_message)

  return

