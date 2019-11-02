
import json
import logging
from ..common import consts, phelper
from ..common.models import PricingResult
from ..common.models import Ec2PriceDimension
from ..ec2 import pricing as ec2pricing
import tinydb

log = logging.getLogger()
regiondbs = {}
indexMetadata = {}


def calculate(pdim):

  log.info("Calculating Redshift pricing with the following inputs: {}".format(str(pdim.__dict__)))

  ts = phelper.Timestamp()
  ts.start('totalCalculation')
  ts.start('tinyDbLoadOnDemand')
  ts.start('tinyDbLoadReserved')

  awsPriceListApiVersion = ''
  cost = 0
  pricing_records = []
  priceQuery = tinydb.Query()

  global regiondbs
  global indexMetadata

  #DBs for Data Transfer
  tmpDtDbKey = consts.SERVICE_DATA_TRANSFER+pdim.region+pdim.termType
  dtdbs = regiondbs.get(tmpDtDbKey,{})
  if not dtdbs:
    dtdbs, dtIndexMetadata = phelper.loadDBs(consts.SERVICE_DATA_TRANSFER, phelper.get_partition_keys(consts.SERVICE_DATA_TRANSFER, pdim.region, consts.SCRIPT_TERM_TYPE_ON_DEMAND, **{}))
    regiondbs[tmpDtDbKey]=dtdbs
  #_/_/_/_/_/ ON-DEMAND PRICING _/_/_/_/_/
  #Load On-Demand Redshift DBs
  if pdim.termType == consts.SCRIPT_TERM_TYPE_ON_DEMAND:

    dbs = regiondbs.get(consts.SERVICE_REDSHIFT+pdim.region+consts.TERM_TYPE_ON_DEMAND,{})
    if not dbs:
      dbs, indexMetadata = phelper.loadDBs(consts.SERVICE_REDSHIFT, phelper.get_partition_keys(consts.SERVICE_REDSHIFT, pdim.region, consts.SCRIPT_TERM_TYPE_ON_DEMAND))
      regiondbs[consts.SERVICE_REDSHIFT+pdim.region+pdim.termType]=dbs

    ts.finish('tinyDbLoadOnDemand')
    log.debug("Time to load OnDemand DB files: [{}]".format(ts.elapsed('tinyDbLoadOnDemand')))

    #Redshift Compute Instance
    if pdim.instanceHours:
      computeDb = dbs[phelper.create_file_key((consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[consts.SCRIPT_TERM_TYPE_ON_DEMAND], consts.PRODUCT_FAMILY_COMPUTE_INSTANCE))]
      ts.start('tinyDbSearchComputeFile')
      query = ((priceQuery['Instance Type'] == pdim.instanceType) )

      pricing_records, cost = phelper.calculate_price(consts.SERVICE_REDSHIFT, computeDb, query, pdim.instanceHours, pricing_records, cost)
      log.debug("Time to search compute:[{}]".format(ts.finish('tinyDbSearchComputeFile')))


    #TODO: move Data Transfer to a common file (since now it's a separate index file)
    """
    #Data Transfer
    dataTransferDb = dtdbs[phelper.create_file_key((consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_DATA_TRANSFER))]

    #Out to the Internet
    if pdim.dataTransferOutInternetGb:
      ts.start('searchDataTransfer')
      query = ((priceQuery['To Location'] == 'External') & (priceQuery['Transfer Type'] == 'AWS Outbound'))
      pricing_records, cost = phelper.calculate_price(consts.SERVICE_DATA_TRANSFER, dataTransferDb, query, pdim.dataTransferOutInternetGb, pricing_records, cost)
      log.debug("Time to search AWS Data Transfer Out: [{}]".format(ts.finish('searchDataTransfer')))

    #Intra-regional data transfer - in/out/between EC2 AZs or using EIPs or ELB
    if pdim.dataTransferOutIntraRegionGb:
      query = ((priceQuery['Transfer Type'] == 'IntraRegion'))
      pricing_records, cost = phelper.calculate_price(consts.SERVICE_DATA_TRANSFER, dataTransferDb, query, pdim.dataTransferOutIntraRegionGb, pricing_records, cost)


    #Inter-regional data transfer - out to other AWS regions
    if pdim.dataTransferOutInterRegionGb:
      query = ((priceQuery['Transfer Type'] == 'InterRegion Outbound') & (priceQuery['To Location'] == consts.REGION_MAP[pdim.toRegion]))
      pricing_records, cost = phelper.calculate_price(consts.SERVICE_DATA_TRANSFER, dataTransferDb, query, pdim.dataTransferOutInterRegionGb, pricing_records, cost)
    """

  #_/_/_/_/_/ RESERVED PRICING _/_/_/_/_/

  print("regiondbs[]".format(regiondbs))

  #Load Reserved DBs
  if pdim.termType == consts.SCRIPT_TERM_TYPE_RESERVED:

    indexArgs = {'offeringClasses':consts.EC2_OFFERING_CLASS_MAP.values(),
                 'tenancies':[consts.EC2_TENANCY_SHARED], 'purchaseOptions':consts.EC2_PURCHASE_OPTION_MAP.values()}

    dbs = regiondbs.get(consts.SERVICE_REDSHIFT+pdim.region+pdim.termType,{})
    if not dbs:
        dbs, indexMetadata = phelper.loadDBs(consts.SERVICE_REDSHIFT, phelper.get_partition_keys(consts.SERVICE_REDSHIFT, pdim.region, consts.SCRIPT_TERM_TYPE_RESERVED, **indexArgs))
        regiondbs[consts.SERVICE_REDSHIFT+pdim.region+pdim.termType]=dbs
    ts.finish('tinyDbLoadReserved')
    log.debug("Time to load Reserved DB files: [{}]".format(ts.elapsed('tinyDbLoadReserved')))
    log.debug("regiondbs keys:[{}]".format(regiondbs))

    #Redshift only supports standard
    print("dbs:[{}]".format(dbs))
    computeDb = dbs[phelper.create_file_key((consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType],
                                             consts.PRODUCT_FAMILY_COMPUTE_INSTANCE, consts.EC2_OFFERING_CLASS_STANDARD,
                                             consts.EC2_TENANCY_SHARED, consts.EC2_PURCHASE_OPTION_MAP[pdim.offeringType]))]



    ts.start('tinyDbSearchComputeFileReserved')
    query = ((priceQuery['Instance Type'] == pdim.instanceType) &
             (priceQuery['LeaseContractLength'] == consts.EC2_RESERVED_YEAR_MAP["{}".format(pdim.years)]))

    hrsQuery = query & (priceQuery['Unit'] == 'Hrs' )
    qtyQuery = query & (priceQuery['Unit'] == 'Quantity' )

    if pdim.offeringType in (consts.SCRIPT_EC2_PURCHASE_OPTION_ALL_UPFRONT, consts.SCRIPT_EC2_PURCHASE_OPTION_PARTIAL_UPFRONT):
      pricing_records, cost = phelper.calculate_price(consts.SERVICE_REDSHIFT, computeDb, qtyQuery, pdim.instanceCount, pricing_records, cost)

    if pdim.offeringType in (consts.SCRIPT_EC2_PURCHASE_OPTION_NO_UPFRONT, consts.SCRIPT_EC2_PURCHASE_OPTION_PARTIAL_UPFRONT):
      reservedInstanceHours = pdim.instanceCount * consts.HOURS_IN_MONTH * 12 * pdim.years #TODO: move to common function
      pricing_records, cost = phelper.calculate_price(consts.SERVICE_REDSHIFT, computeDb, hrsQuery, reservedInstanceHours, pricing_records, cost)

    log.debug("Time to search:[{}]".format(ts.finish('tinyDbSearchComputeFileReserved')))

  awsPriceListApiVersion = indexMetadata['Version']
  extraargs = {'priceDimensions':pdim}
  pricing_result = PricingResult(awsPriceListApiVersion, pdim.region, cost, pricing_records, **extraargs)
  log.debug(json.dumps(vars(pricing_result),sort_keys=False,indent=4))

  log.debug("Total time: [{}]".format(ts.finish('totalCalculation')))
  return pricing_result.__dict__
