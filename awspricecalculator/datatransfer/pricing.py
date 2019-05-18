
import json
import logging
from ..common import consts, phelper
from ..common.models import PricingResult
import tinydb

log = logging.getLogger()
regiondbs = {}
indexMetadata = {}


def calculate(pdim):

  log.info("Calculating AWSDataTransfer pricing with the following inputs: {}".format(str(pdim.__dict__)))

  ts = phelper.Timestamp()
  ts.start('totalCalculation')
  ts.start('tinyDbLoadOnDemand')

  awsPriceListApiVersion = ''
  cost = 0
  pricing_records = []
  priceQuery = tinydb.Query()

  global regiondbs
  global indexMetadata

  #Load On-Demand DBs
  indexArgs = {}
  tmpDbKey = consts.SERVICE_DATA_TRANSFER+pdim.region+pdim.termType+pdim.tenancy
  dbs = regiondbs.get(tmpDbKey,{})
  if not dbs:
    dbs, indexMetadata = phelper.loadDBs(consts.SERVICE_DATA_TRANSFER, phelper.get_partition_keys(consts.SERVICE_DATA_TRANSFER, pdim.region, consts.SCRIPT_TERM_TYPE_ON_DEMAND, **indexArgs))
    regiondbs[tmpDbKey]=dbs

  ts.finish('tinyDbLoadOnDemand')
  log.debug("Time to load OnDemand DB files: [{}]".format(ts.elapsed('tinyDbLoadOnDemand')))

  #Data Transfer
  dataTransferDb = dbs[phelper.create_file_key((consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_DATA_TRANSFER))]

  #Out to the Internet
  if pdim.dataTransferOutInternetGb:
    ts.start('searchDataTransfer')
    query = ((priceQuery['To Location'] == 'External') & (priceQuery['Transfer Type'] == 'AWS Outbound'))
    pricing_records, cost = phelper.calculate_price(consts.SERVICE_DATA_TRANSFER, dataTransferDb, query, pdim.dataTransferOutInternetGb, pricing_records, cost)
    log.debug("Time to search AWSDataTransfer data transfer Out: [{}]".format(ts.finish('searchDataTransfer')))

  #Intra-regional data transfer - in/out/between AZs or using EIPs or ELB
  if pdim.dataTransferOutIntraRegionGb:
    query = ((priceQuery['Transfer Type'] == 'IntraRegion'))
    pricing_records, cost = phelper.calculate_price(consts.SERVICE_DATA_TRANSFER, dataTransferDb, query, pdim.dataTransferOutIntraRegionGb, pricing_records, cost)

  #Inter-regional data transfer - out to other AWS regions
  if pdim.dataTransferOutInterRegionGb:
    query = ((priceQuery['Transfer Type'] == 'InterRegion Outbound') & (priceQuery['To Location'] == consts.REGION_MAP[pdim.toRegion]))
    pricing_records, cost = phelper.calculate_price(consts.SERVICE_DATA_TRANSFER, dataTransferDb, query, pdim.dataTransferOutInterRegionGb, pricing_records, cost)


  log.debug("regiondbs:[{}]".format(regiondbs.keys()))
  awsPriceListApiVersion = indexMetadata['Version']
  extraargs = {'priceDimensions':pdim}
  pricing_result = PricingResult(awsPriceListApiVersion, pdim.region, cost, pricing_records, **extraargs)
  log.debug(json.dumps(vars(pricing_result),sort_keys=False,indent=4))

  log.debug("Total time: [{}]".format(ts.finish('totalCalculation')))
  return pricing_result.__dict__
