import os, sys
import json
import logging
from ..common import consts, phelper
from ..common.models import PricingResult
import tinydb

log = logging.getLogger()

def calculate(pdim):
  ts = phelper.Timestamp()
  ts.start('totalCalculation')

  log.info("Calculating RDS pricing with the following inputs: {}".format(str(pdim.__dict__)))

  #Load On-Demand DBs
  dbs, indexMetadata = phelper.loadDBs(consts.SERVICE_RDS, phelper.get_partition_keys(pdim.region, consts.SCRIPT_TERM_TYPE_ON_DEMAND))
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
    instanceDb = dbs[phelper.create_file_key([consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_DATABASE_INSTANCE])]

    deploymentOptionCondition = pdim.deploymentOption
    if 'sqlserver' in pdim.engine and pdim.deploymentOption == consts.RDS_DEPLOYMENT_OPTION_MULTI_AZ:
      deploymentOptionCondition = consts.RDS_DEPLOYMENT_OPTION_MULTI_AZ_MIRROR

    query = ((priceQuery['Product Family'] == consts.PRODUCT_FAMILY_DATABASE_INSTANCE) &
            (priceQuery['Instance Type'] == pdim.dbInstanceClass) &
            (priceQuery['Database Engine'] == skuEngine) &
            (priceQuery['Database Edition'] == skuEngineEdition) &
            (priceQuery['License Model'] == skuLicenseModel) &
            (priceQuery['Deployment Option'] == deploymentOptionCondition)
            )

    pricing_records, cost = phelper.calculate_price(consts.SERVICE_RDS, instanceDb, query, pdim.instanceHours, pricing_records, cost)

  #TODO: add support for Reserved
  #Reserved

  #Data Transfer
  #To internet
  if pdim.dataTransferOutInternetGb:
    dataTransferDb = dbs[phelper.create_file_key([consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_DATA_TRANSFER])]
    query = ((priceQuery['serviceCode'] == consts.SERVICE_CODE_AWS_DATA_TRANSFER) &
            (priceQuery['To Location'] == 'External') &
            (priceQuery['Transfer Type'] == 'AWS Outbound'))

    pricing_records, cost = phelper.calculate_price(consts.SERVICE_RDS, dataTransferDb, query, pdim.dataTransferOutInternetGb, pricing_records, cost)


  #Inter-regional data transfer - to other AWS regions
  if pdim.dataTransferOutInterRegionGb:
    dataTransferDb = dbs[phelper.create_file_key([consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_DATA_TRANSFER])]
    query = ((priceQuery['serviceCode'] == consts.SERVICE_CODE_AWS_DATA_TRANSFER) &
            (priceQuery['To Location'] == consts.REGION_MAP[pdim.toRegion]) &
            (priceQuery['Transfer Type'] == 'InterRegion Outbound'))

    pricing_records, cost = phelper.calculate_price(consts.SERVICE_RDS, dataTransferDb, query, pdim.dataTransferOutInterRegionGb, pricing_records, cost)

  #Storage (magnetic, SSD, PIOPS)
  if pdim.storageGbMonth:
    engineCondition = 'Any'
    if skuEngine == consts.RDS_DB_ENGINE_SQL_SERVER: engineCondition = consts.RDS_DB_ENGINE_SQL_SERVER
    storageDb = dbs[phelper.create_file_key([consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_DB_STORAGE])]
    query = ((priceQuery['Volume Type'] == pdim.volumeType) &
             (priceQuery['Database Engine'] == engineCondition) &
             (priceQuery['Deployment Option'] == pdim.deploymentOption))

    pricing_records, cost = phelper.calculate_price(consts.SERVICE_RDS, storageDb, query, pdim.storageGbMonth, pricing_records, cost)

  #Provisioned IOPS
  if pdim.storageType == consts.SCRIPT_RDS_STORAGE_TYPE_IO1:
    iopsDb = dbs[phelper.create_file_key([consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_DB_PIOPS])]
    query = ((priceQuery['Deployment Option'] == pdim.deploymentOption))
    pricing_records, cost = phelper.calculate_price(consts.SERVICE_RDS, iopsDb, query, pdim.iops, pricing_records, cost)

  #Consumed IOPS (I/O rate)
  if pdim.ioRequests:
    sysopsDb = dbs[phelper.create_file_key([consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_SYSTEM_OPERATION])]
    dbEngineCondition = 'Any'
    if pdim.engine in (consts.RDS_DB_ENGINE_POSTGRESQL, consts.RDS_DB_ENGINE_AURORA_MYSQL):
      dbEngineCondition = pdim.engine

    query = ((priceQuery['Group'] == 'Aurora I/O Operation')&
             (priceQuery['Database Engine'] == dbEngineCondition)
             )
    pricing_records, cost = phelper.calculate_price(consts.SERVICE_RDS, sysopsDb, query, pdim.ioRequests, pricing_records, cost)


  if pdim.backupStorageGbMonth:
    snapshotDb = dbs[phelper.create_file_key([consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_SNAPSHOT])]
    query = ((priceQuery['usageType'] == 'RDS:ChargedBackupUsage'))
    pricing_records, cost = phelper.calculate_price(consts.SERVICE_RDS, snapshotDb, query, pdim.backupStorageGbMonth, pricing_records, cost)


  log.debug("Total time to calculate price: [{}]".format(ts.finish('totalCalculation')))
  pricing_result = PricingResult(awsPriceListApiVersion, pdim.region, cost, pricing_records)
  log.debug(json.dumps(vars(pricing_result),sort_keys=False,indent=4))
  return pricing_result.__dict__
