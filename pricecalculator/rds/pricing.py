import json
import logging
import os, sys
from ..common import consts, phelper
from ..common.errors import ValidationError
from ..common.data import PricingResult, PricingRecord

log = logging.getLogger()


def calculate(pdim):
  log.info("Calculating RDS pricing with the following inputs: {}".format(str(pdim.__dict__)))

  skuEngine = ''
  skuEngineEdition = ''
  skuLicenseModel = ''

  if pdim.engine in consts.RDS_ENGINE_MAP:
    skuEngine = consts.RDS_ENGINE_MAP[pdim.engine]['engine']
    skuEngineEdition = consts.RDS_ENGINE_MAP[pdim.engine]['edition']
    skuLicenseModel = consts.RDS_LICENSE_MODEL_MAP[pdim.licenseModel]

  __location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
  index_file = open(os.path.join(__location__, 'index.json')).read();
  price_data = json.loads(index_file)
  awsPriceListApiVersion = price_data['version']

  cost = 0
  pricing_records = []
  skus = phelper.get_skus(price_data, region=pdim.region)
  #print("SKUs to evaluate:["+str(len(skus))+"]")
  #print("size of price_data:["+str(sys.getsizeof(price_data))+"] - size of skus:["+ str(sys.getsizeof(skus))+"]")
  #phelper.get_distinct_product_attributes(price_data, 'usagetype',region=pdim.region)


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
        usageUnits = pdim.instanceHours
        dbMatch = False
        if 'databaseEdition' in sku_data['attributes']:
          if pdim.dbInstanceClass == sku_data['attributes']['instanceType'] \
                and skuEngine == sku_data['attributes']['databaseEngine'] \
                and skuEngineEdition == sku_data['attributes']['databaseEdition']\
                and skuLicenseModel == sku_data['attributes']['licenseModel']:
            dbMatch = True
        else:
          if pdim.dbInstanceClass == sku_data['attributes']['instanceType'] \
                and skuEngine == sku_data['attributes']['databaseEngine'] \
                and skuLicenseModel == sku_data['attributes']['licenseModel']:
            dbMatch = True

        if dbMatch:
          #Multi/Single AZ
          if pdim.deploymentOption == sku_data['attributes']['deploymentOption']:
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
      #TODO: PriceList API doesn't have records for "General Purpose - Aurora" in multi-az deployment
      if pdim.storageGbMonth and sku_data['productFamily'] == consts.PRODUCT_FAMILY_DB_STORAGE \
              and sku_data['attributes']['volumeType'] == pdim.volumeType\
              and sku_data['attributes']['deploymentOption'] == pdim.deploymentOption:
        usageUnits = pdim.storageGbMonth
        amt = pricePerUnit * float(usageUnits)

      #Provisioned IOPS
      #TODO: add support for SQL Server Multi-AZ mirror
      #TODO: exclude Aurora, since Aurora only pays for consumed I/O, not IOPS
      if sku_data['productFamily'] == consts.PRODUCT_FAMILY_DB_PIOPS:
        usageUnits = pdim.iops
        if 'group' in sku_data['attributes']:
          if sku_data['attributes']['group'] == 'RDS-PIOPS' and sku_data['attributes']['deploymentOption'] == pdim.deploymentOption:
            amt = pricePerUnit * float(usageUnits)

      #Consumed IOPS (I/O rate) - only applicable for Aurora
      if skuEngine == consts.RDS_DB_ENGINE_AURORA:
        if 'group' in sku_data['attributes']:
          if sku_data['attributes']['group'] == 'RDS I/O Operation':
            usageUnits = pdim.ioRate
            amt = pricePerUnit * float(usageUnits)


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

  pricing_result = PricingResult(awsPriceListApiVersion, pdim.region, cost, pricing_records)
  log.debug(json.dumps(vars(pricing_result),sort_keys=False,indent=4))
  return pricing_result.__dict__

