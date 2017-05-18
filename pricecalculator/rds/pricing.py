import os, sys
import json
import logging
from ..common import consts, phelper
from ..common.data import PricingResult
import tinydb

log = logging.getLogger()


def calculate(pdim):
  ts = phelper.Timestamp()
  ts.start('totalCalculation')

  log.info("Calculating RDS pricing with the following inputs: {}".format(str(pdim.__dict__)))
  #print("Calculating RDS pricing with the following inputs: {}".format(str(pdim.__dict__)))


  dbs, indexMetadata = phelper.loadDBs(consts.SERVICE_RDS, phelper.get_partition_keys(pdim.region))
  cost = 0
  pricing_records = []

  awsPriceListApiVersion = indexMetadata['Version']
  priceQuery = tinydb.Query()


  skuEngine = ''
  skuEngineEdition = ''
  skuLicenseModel = ''

  if pdim.engine in consts.RDS_ENGINE_MAP:
    skuEngine = consts.RDS_ENGINE_MAP[pdim.engine]['engine']
    skuEngineEdition = consts.RDS_ENGINE_MAP[pdim.engine]['edition']
    skuLicenseModel = consts.RDS_LICENSE_MODEL_MAP[pdim.licenseModel]

  #DB Instance
  if pdim.instanceHours:
    instanceDb = dbs[phelper.create_file_key(consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_DATABASE_INSTANCE)]
    query = ((priceQuery['Product Family'] == consts.PRODUCT_FAMILY_DATABASE_INSTANCE) &
            (priceQuery['Instance Type'] == pdim.dbInstanceClass) &
            (priceQuery['Database Engine'] == skuEngine) &
            (priceQuery['Database Edition'] == skuEngineEdition) &
            (priceQuery['License Model'] == skuLicenseModel) &
            (priceQuery['Deployment Option'] == pdim.deploymentOption))

    pricing_records, cost = phelper.calculate_price(consts.SERVICE_RDS, instanceDb, query, pdim.instanceHours, pricing_records, cost)

  #TODO: add support for Reserved
  #Reserved

  #Data Transfer
  #To internet
  if pdim.dataTransferOutInternetGb:
    dataTransferDb = dbs[phelper.create_file_key(consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_DATA_TRANSFER)]
    query = ((priceQuery['serviceCode'] == consts.SERVICE_CODE_AWS_DATA_TRANSFER) &
            (priceQuery['To Location'] == 'External') &
            (priceQuery['Transfer Type'] == 'AWS Outbound'))

    pricing_records, cost = phelper.calculate_price(consts.SERVICE_RDS, dataTransferDb, query, pdim.dataTransferOutInternetGb, pricing_records, cost)


  #Inter-regional data transfer - to other AWS regions
  if pdim.dataTransferOutInterRegionGb:
    dataTransferDb = dbs[phelper.create_file_key(consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_DATA_TRANSFER)]
    query = ((priceQuery['serviceCode'] == consts.SERVICE_CODE_AWS_DATA_TRANSFER) &
            (priceQuery['To Location'] == consts.REGION_MAP[pdim.toRegion]) &
            (priceQuery['Transfer Type'] == 'InterRegion Outbound'))

    pricing_records, cost = phelper.calculate_price(consts.SERVICE_RDS, dataTransferDb, query, pdim.dataTransferOutInterRegionGb, pricing_records, cost)


  #Ohio is the only region where AWS has published data for storage, snapshots and pIops
  #TODO: Implement for all product families once AWS publishes data for all regions

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
  if sku_data['productFamily'] == consts.PRODUCT_FAMILY_SNAPSHOT:
    service = consts.SERVICE_EBS
    if 'EBS:SnapshotUsage' in sku_data['attributes']['usagetype']: usageUnits = ebsSnapshotGbMonth
    amt = pricePerUnit * usageUnits

  if amt > 0:
    cost = cost + amt
    if billableBand > 0: usageUnits = billableBand
    pricing_record = PricingRecord(service,round(amt,4),p['description'],pricePerUnit,usageUnits,p['rateCode'])
    pricing_records.append(vars(pricing_record))
  """

  print "Total time to calculate price: [{}]".format(ts.finish('totalCalculation'))
  pricing_result = PricingResult(awsPriceListApiVersion, pdim.region, cost, pricing_records)
  log.debug(json.dumps(vars(pricing_result),sort_keys=False,indent=4))
  return pricing_result.__dict__

