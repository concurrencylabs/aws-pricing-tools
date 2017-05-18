
import json
import logging
from ..common import consts, phelper
from ..common.data import PricingResult
import tinydb

log = logging.getLogger()


def calculate(pdim):

  log.info("Calculating Lambda pricing with the following inputs: {}".format(str(pdim.__dict__)))
  #print("Calculating Lambda pricing with the following inputs: {}".format(str(pdim.__dict__)))

  ts = phelper.Timestamp()
  ts.start('totalCalculationAwsLambda')

  dbs, indexMetadata = phelper.loadDBs(consts.SERVICE_LAMBDA, phelper.get_partition_keys(pdim.region))

  cost = 0
  pricing_records = []

  awsPriceListApiVersion = indexMetadata['Version']
  priceQuery = tinydb.Query()

  #TODO:calculate free-tier (include a flag)

  serverlessDb = dbs[phelper.create_file_key(consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_SERVERLESS)]

  #Requests
  if pdim.requestCount:
    query = ((priceQuery['Group'] == 'AWS-Lambda-Requests'))
    pricing_records, cost = phelper.calculate_price(consts.SERVICE_LAMBDA, serverlessDb, query, pdim.requestCount, pricing_records, cost)

  #GB-s (aka compute time)
  if pdim.avgDurationMs:
    query = ((priceQuery['Group'] == 'AWS-Lambda-Duration'))
    usageUnits = pdim.requestCount * (float(pdim.avgDurationMs) / 1000) * (float(pdim.memoryMb) / 1024)
    pricing_records, cost = phelper.calculate_price(consts.SERVICE_LAMBDA, serverlessDb, query, usageUnits, pricing_records, cost)

  #Data Transfer
  dataTransferDb = dbs[phelper.create_file_key(consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_DATA_TRANSFER)]

  #To internet
  if pdim.dataTransferOutInternetGb:
    query = ((priceQuery['To Location'] == 'External') & (priceQuery['Transfer Type'] == 'AWS Outbound'))
    pricing_records, cost = phelper.calculate_price(consts.SERVICE_LAMBDA, dataTransferDb, query, pdim.dataTransferOutInternetGb, pricing_records, cost)

  #Intra-regional data transfer - in/out/between EC2 AZs or using IPs or ELB
  if pdim.dataTransferOutIntraRegionGb:
    query = ((priceQuery['Transfer Type'] == 'IntraRegion'))
    pricing_records, cost = phelper.calculate_price(consts.SERVICE_LAMBDA, dataTransferDb, query, pdim.dataTransferOutIntraRegionGb, pricing_records, cost)

  #Inter-regional data transfer - out to other AWS regions
  if pdim.dataTransferOutInterRegionGb:
    query = ((priceQuery['Transfer Type'] == 'InterRegion Outbound') & (priceQuery['To Location'] == consts.REGION_MAP[pdim.toRegion]))
    pricing_records, cost = phelper.calculate_price(consts.SERVICE_LAMBDA, dataTransferDb, query, pdim.dataTransferOutInterRegionGb, pricing_records, cost)


  pricing_result = PricingResult(awsPriceListApiVersion, pdim.region, cost, pricing_records)
  log.debug(json.dumps(vars(pricing_result),sort_keys=False,indent=4))

  log.debug("Total time to compute: [{}]".format(ts.finish('totalCalculationAwsLambda')))
  return pricing_result.__dict__


