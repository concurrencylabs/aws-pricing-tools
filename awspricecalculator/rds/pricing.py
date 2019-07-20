import os, sys
import json
import logging
from ..common import consts, phelper, utils
from ..common.models import PricingResult
import tinydb

log = logging.getLogger()
regiondbs = {}
indexMetadata = {}


def calculate(pdim):
  ts = phelper.Timestamp()
  ts.start('totalCalculation')
  ts.start('tinyDbLoadOnDemand')
  ts.start('tinyDbLoadReserved')

  global regiondbs
  global indexMetadata


  log.info("Calculating RDS pricing with the following inputs: {}".format(str(pdim.__dict__)))

  #Load On-Demand DBs
  dbs, indexMetadata = phelper.loadDBs(consts.SERVICE_RDS, phelper.get_partition_keys(consts.SERVICE_RDS, pdim.region, consts.SCRIPT_TERM_TYPE_ON_DEMAND))
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

  deploymentOptionCondition = pdim.deploymentOption

  #'Multi-AZ (SQL Server Mirror)' is no longer available in pricing index
  #if 'sqlserver' in pdim.engine and pdim.deploymentOption == consts.RDS_DEPLOYMENT_OPTION_MULTI_AZ:
  #  deploymentOptionCondition = consts.RDS_DEPLOYMENT_OPTION_MULTI_AZ_MIRROR

  #DBs for Data Transfer
  tmpDtDbKey = consts.SERVICE_DATA_TRANSFER+pdim.region+pdim.termType
  dtdbs = regiondbs.get(tmpDtDbKey,{})
  if not dtdbs:
    dtdbs, dtIndexMetadata = phelper.loadDBs(consts.SERVICE_DATA_TRANSFER, phelper.get_partition_keys(consts.SERVICE_DATA_TRANSFER, pdim.region, consts.SCRIPT_TERM_TYPE_ON_DEMAND, **{}))
    regiondbs[tmpDtDbKey]=dtdbs


  #_/_/_/_/_/ ON-DEMAND PRICING _/_/_/_/_/
  if pdim.termType == consts.SCRIPT_TERM_TYPE_ON_DEMAND:
    #Load On-Demand DBs
    dbs = regiondbs.get(consts.SERVICE_RDS+pdim.region+pdim.termType,{})
    if not dbs:
        dbs, indexMetadata = phelper.loadDBs(consts.SERVICE_RDS, phelper.get_partition_keys(consts.SERVICE_RDS, pdim.region, consts.SCRIPT_TERM_TYPE_ON_DEMAND))
        regiondbs[consts.SERVICE_RDS+pdim.region+pdim.termType]=dbs

    ts.finish('tinyDbLoadOnDemand')
    log.debug("Time to load OnDemand DB files: [{}]".format(ts.elapsed('tinyDbLoadOnDemand')))

    #DB Instance
    if pdim.instanceHours:
      instanceDb = dbs[phelper.create_file_key((consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_DATABASE_INSTANCE))]


      ts.start('tinyDbSearchComputeFile')
      query = ((priceQuery['Product Family'] == consts.PRODUCT_FAMILY_DATABASE_INSTANCE) &
              (priceQuery['Instance Type'] == pdim.dbInstanceClass) &
              (priceQuery['Database Engine'] == skuEngine) &
              (priceQuery['Database Edition'] == skuEngineEdition) &
              (priceQuery['License Model'] == skuLicenseModel) &
              (priceQuery['Deployment Option'] == deploymentOptionCondition)
              )

      log.debug("Time to search DB instance compute:[{}]".format(ts.finish('tinyDbSearchComputeFile')))
      pricing_records, cost = phelper.calculate_price(consts.SERVICE_RDS, instanceDb, query, pdim.instanceHours, pricing_records, cost)

    #Data Transfer
    #To internet
    if pdim.dataTransferOutInternetGb:
      dataTransferDb = dtdbs[phelper.create_file_key((consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_DATA_TRANSFER))]
      query = ((priceQuery['serviceCode'] == consts.SERVICE_CODE_AWS_DATA_TRANSFER) &
              (priceQuery['To Location'] == 'External') &
              (priceQuery['Transfer Type'] == 'AWS Outbound'))

      pricing_records, cost = phelper.calculate_price(consts.SERVICE_DATA_TRANSFER, dataTransferDb, query, pdim.dataTransferOutInternetGb, pricing_records, cost)


    #Inter-regional data transfer - to other AWS regions
    if pdim.dataTransferOutInterRegionGb:
      dataTransferDb = dtdbs[phelper.create_file_key((consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_DATA_TRANSFER))]
      query = ((priceQuery['serviceCode'] == consts.SERVICE_CODE_AWS_DATA_TRANSFER) &
              (priceQuery['To Location'] == consts.REGION_MAP[pdim.toRegion]) &
              (priceQuery['Transfer Type'] == 'InterRegion Outbound'))

      pricing_records, cost = phelper.calculate_price(consts.SERVICE_DATA_TRANSFER, dataTransferDb, query, pdim.dataTransferOutInterRegionGb, pricing_records, cost)

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


    #Snapshot Storage
    if pdim.backupStorageGbMonth:
      snapshotDb = dbs[phelper.create_file_key([consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_SNAPSHOT])]
      query = ((priceQuery['usageType'] == 'RDS:ChargedBackupUsage'))
      pricing_records, cost = phelper.calculate_price(consts.SERVICE_RDS, snapshotDb, query, pdim.backupStorageGbMonth, pricing_records, cost)




  #_/_/_/_/_/ RESERVED PRICING _/_/_/_/_/
  if pdim.termType == consts.SCRIPT_TERM_TYPE_RESERVED:
    #Load Reserved DBs

    indexArgs = {'offeringClasses':consts.EC2_OFFERING_CLASS_MAP.values(),
                 'tenancies':[consts.EC2_TENANCY_SHARED], 'purchaseOptions':consts.EC2_PURCHASE_OPTION_MAP.values()}

    dbs = regiondbs.get(consts.SERVICE_RDS+pdim.region+pdim.termType,{})
    if not dbs:
        dbs, indexMetadata = phelper.loadDBs(consts.SERVICE_RDS, phelper.get_partition_keys(consts.SERVICE_RDS, pdim.region, consts.SCRIPT_TERM_TYPE_RESERVED, **indexArgs))
        regiondbs[consts.SERVICE_RDS+pdim.region+pdim.termType]=dbs
    ts.finish('tinyDbLoadReserved')
    log.debug("Time to load Reserved DB files: [{}]".format(ts.elapsed('tinyDbLoadReserved')))
    log.debug("regiondbs keys:[{}]".format(regiondbs))

    #DB Instance
    #RDS only supports standard
    instanceDb = dbs[phelper.create_file_key((consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType],
                                             consts.PRODUCT_FAMILY_DATABASE_INSTANCE, consts.EC2_OFFERING_CLASS_STANDARD,
                                             consts.EC2_TENANCY_SHARED, consts.EC2_PURCHASE_OPTION_MAP[pdim.offeringType]))]


    ts.start('tinyDbSearchComputeFileReserved')
    query = ((priceQuery['Product Family'] == consts.PRODUCT_FAMILY_DATABASE_INSTANCE) &
            (priceQuery['Instance Type'] == pdim.dbInstanceClass) &
            (priceQuery['Database Engine'] == skuEngine) &
            (priceQuery['Database Edition'] == skuEngineEdition) &
            (priceQuery['License Model'] == skuLicenseModel) &
            (priceQuery['Deployment Option'] == deploymentOptionCondition) &
            (priceQuery['OfferingClass'] == consts.EC2_OFFERING_CLASS_MAP[pdim.offeringClass]) &
            (priceQuery['PurchaseOption'] == consts.EC2_PURCHASE_OPTION_MAP[pdim.offeringType]) &
            (priceQuery['LeaseContractLength'] == consts.EC2_RESERVED_YEAR_MAP["{}".format(pdim.years)])
            )

    hrsQuery = query & (priceQuery['Unit'] == 'Hrs' )
    qtyQuery = query & (priceQuery['Unit'] == 'Quantity' )

    #TODO: use RDS-specific constants, not EC2 constants
    if pdim.offeringType in (consts.SCRIPT_EC2_PURCHASE_OPTION_ALL_UPFRONT, consts.SCRIPT_EC2_PURCHASE_OPTION_PARTIAL_UPFRONT):
      pricing_records, cost = phelper.calculate_price(consts.SERVICE_RDS, instanceDb, qtyQuery, pdim.instanceCount, pricing_records, cost)

    if pdim.offeringType in (consts.SCRIPT_EC2_PURCHASE_OPTION_NO_UPFRONT, consts.SCRIPT_EC2_PURCHASE_OPTION_PARTIAL_UPFRONT):
      reservedInstanceHours = utils.calculate_instance_hours_year(pdim.instanceCount, pdim.years)
      pricing_records, cost = phelper.calculate_price(consts.SERVICE_RDS, instanceDb, hrsQuery, reservedInstanceHours, pricing_records, cost)

    log.debug("Time to search DB instance compute:[{}]".format(ts.finish('tinyDbSearchComputeFileReserved')))





  log.debug("Total time to calculate price: [{}]".format(ts.finish('totalCalculation')))
  extraargs = {'priceDimensions':pdim}
  pricing_result = PricingResult(awsPriceListApiVersion, pdim.region, cost, pricing_records, **extraargs)
  log.debug(json.dumps(vars(pricing_result),sort_keys=False,indent=4))
  return pricing_result.__dict__
