
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

  log.info("Calculating EMR pricing with the following inputs: {}".format(str(pdim.__dict__)))

  ts = phelper.Timestamp()
  ts.start('totalCalculation')
  ts.start('tinyDbLoadOnDemand')

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
  #Load On-Demand EMR DBs
  dbs = regiondbs.get(consts.SERVICE_EMR+pdim.region+consts.TERM_TYPE_ON_DEMAND,{})
  if not dbs:
    dbs, indexMetadata = phelper.loadDBs(consts.SERVICE_EMR, phelper.get_partition_keys(consts.SERVICE_EMR, pdim.region, consts.SCRIPT_TERM_TYPE_ON_DEMAND))
    regiondbs[consts.SERVICE_EMR+pdim.region+pdim.termType]=dbs

  ts.finish('tinyDbLoadOnDemand')
  log.debug("Time to load OnDemand DB files: [{}]".format(ts.elapsed('tinyDbLoadOnDemand')))

  #EMR Compute Instance
  if pdim.instanceHours:
    #The EMR component in the calculation always uses OnDemand (Reserved it not supported yet for EMR)
    computeDb = dbs[phelper.create_file_key((consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[consts.SCRIPT_TERM_TYPE_ON_DEMAND], consts.PRODUCT_FAMILY_EMR_INSTANCE))]
    ts.start('tinyDbSearchComputeFile')
    #TODO: add support for Hunk Software Type
    query = ((priceQuery['Instance Type'] == pdim.instanceType) & (priceQuery['Software Type'] == 'EMR'))

    pricing_records, cost = phelper.calculate_price(consts.SERVICE_EMR, computeDb, query, pdim.instanceHours, pricing_records, cost)
    log.debug("Time to search compute:[{}]".format(ts.finish('tinyDbSearchComputeFile')))


  #EC2 Pricing - the EC2 component takes into consideration either OnDemand or Reserved.
  ec2_pricing = ec2pricing.calculate(Ec2PriceDimension(**pdim.ec2PriceDims))
  log.info("pdim.ec2PriceDims:[{}]".format(pdim.ec2PriceDims))
  log.info("ec2_pricing:[{}]".format(ec2_pricing))
  if ec2_pricing.get('pricingRecords',[]): pricing_records.extend(ec2_pricing['pricingRecords'])
  cost += ec2_pricing.get('totalCost',0)


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


  """
  #Load Reserved DBs
  if pdim.termType == consts.SCRIPT_TERM_TYPE_RESERVED:
    indexArgs = {'offeringClasses':[consts.EC2_OFFERING_CLASS_MAP[pdim.offeringClass]],
                 'tenancies':[consts.EC2_TENANCY_MAP[pdim.tenancy]], 'purchaseOptions':[consts.EC2_PURCHASE_OPTION_MAP[pdim.offeringType]]}
    #Load all values for offeringClasses, tenancies and purchaseOptions
    #indexArgs = {'offeringClasses':consts.EC2_OFFERING_CLASS_MAP.values(),
    #             'tenancies':consts.EC2_TENANCY_MAP.values(), 'purchaseOptions':consts.EC2_PURCHASE_OPTION_MAP.values()}
    tmpDbKey = consts.SERVICE_EC2+pdim.region+pdim.termType+pdim.offeringClass+pdim.tenancy+pdim.offeringType
    #tmpDbKey = consts.SERVICE_EC2+pdim.region+pdim.termType
    dbs = regiondbs.get(tmpDbKey,{})
    if not dbs:
      dbs, indexMetadata = phelper.loadDBs(consts.SERVICE_EC2, phelper.get_partition_keys(consts.SERVICE_EC2, pdim.region, consts.SCRIPT_TERM_TYPE_RESERVED, **indexArgs))
      #regiondbs[consts.SERVICE_EC2+pdim.region+pdim.termType]=dbs
      regiondbs[tmpDbKey]=dbs

    log.debug("dbs keys:{}".format(dbs.keys()))

    ts.finish('tinyDbLoadReserved')
    log.debug("Time to load Reserved DB files: [{}]".format(ts.elapsed('tinyDbLoadReserved')))


    computeDb = dbs[phelper.create_file_key((consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType],
                                             consts.PRODUCT_FAMILY_COMPUTE_INSTANCE, pdim.offeringClass,
                                             consts.EC2_TENANCY_SHARED, consts.EC2_PURCHASE_OPTION_MAP[pdim.offeringType]))]

    ts.start('tinyDbSearchComputeFileReserved')
    query = ((priceQuery['Instance Type'] == pdim.instanceType) &
            (priceQuery['Operating System'] == consts.EC2_OPERATING_SYSTEMS_MAP[pdim.operatingSystem]) &
            (priceQuery['Tenancy'] == consts.EC2_TENANCY_SHARED) &
            (priceQuery['Pre Installed S/W'] == pdim.preInstalledSoftware) &
            (priceQuery['License Model'] == consts.EC2_LICENSE_MODEL_MAP[pdim.licenseModel]) &
            (priceQuery['OfferingClass'] == consts.EC2_OFFERING_CLASS_MAP[pdim.offeringClass]) &
            (priceQuery['PurchaseOption'] == consts.EC2_PURCHASE_OPTION_MAP[pdim.offeringType] ) &
            (priceQuery['LeaseContractLength'] == consts.EC2_RESERVED_YEAR_MAP["{}".format(pdim.years)] ))

    hrsQuery = query & (priceQuery['Unit'] == 'Hrs' )
    qtyQuery = query & (priceQuery['Unit'] == 'Quantity' )

    if pdim.offeringType in (consts.SCRIPT_EC2_PURCHASE_OPTION_ALL_UPFRONT, consts.SCRIPT_EC2_PURCHASE_OPTION_PARTIAL_UPFRONT):
      pricing_records, cost = phelper.calculate_price(consts.SERVICE_EC2, computeDb, qtyQuery, pdim.instanceCount, pricing_records, cost)

    if pdim.offeringType in (consts.SCRIPT_EC2_PURCHASE_OPTION_NO_UPFRONT, consts.SCRIPT_EC2_PURCHASE_OPTION_PARTIAL_UPFRONT):
      reservedInstanceHours = pdim.instanceCount * consts.HOURS_IN_MONTH * 12 * pdim.years
      pricing_records, cost = phelper.calculate_price(consts.SERVICE_EC2, computeDb, hrsQuery, reservedInstanceHours, pricing_records, cost)


    log.debug("Time to search:[{}]".format(ts.finish('tinyDbSearchComputeFileReserved')))
    """


  log.debug("regiondbs:[{}]".format(regiondbs.keys()))
  awsPriceListApiVersion = indexMetadata['Version']
  pricing_result = PricingResult(awsPriceListApiVersion, pdim.region, cost, pricing_records)
  log.debug(json.dumps(vars(pricing_result),sort_keys=False,indent=4))

  #proc = psutil.Process()
  #log.debug("open_files: {}".format(proc.open_files()))

  log.debug("Total time: [{}]".format(ts.finish('totalCalculation')))
  return pricing_result.__dict__
