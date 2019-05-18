
import json
import logging
from ..common import consts, phelper
from ..common.models import PricingResult
import tinydb

log = logging.getLogger()
regiondbs = {}
indexMetadata = {}


def calculate(pdim):

  log.info("Calculating DynamoDB pricing with the following inputs: {}".format(str(pdim.__dict__)))
  global regiondbs
  global indexMetadata

  ts = phelper.Timestamp()
  ts.start('totalCalculationDynamoDB')

  #Load On-Demand DBs
  dbs = regiondbs.get(consts.SERVICE_DYNAMODB+pdim.region+pdim.termType,{})
  if not dbs:
    dbs, indexMetadata = phelper.loadDBs(consts.SERVICE_DYNAMODB, phelper.get_partition_keys(consts.SERVICE_DYNAMODB, pdim.region,consts.SCRIPT_TERM_TYPE_ON_DEMAND))
    regiondbs[consts.SERVICE_DYNAMODB+pdim.region+pdim.termType]=dbs

  cost = 0
  pricing_records = []

  awsPriceListApiVersion = indexMetadata['Version']
  priceQuery = tinydb.Query()

  #TODO:add support for free-tier flag (include or exclude from calculation)

  iopsDb = dbs[phelper.create_file_key([consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_DB_PIOPS])]

  #Read Capacity Units
  query = ((priceQuery['Group'] == 'DDB-ReadUnits'))
  pricing_records, cost = phelper.calculate_price(consts.SERVICE_DYNAMODB, iopsDb, query, pdim.readCapacityUnitHours, pricing_records, cost)

  #Write Capacity Units
  query = ((priceQuery['Group'] == 'DDB-WriteUnits'))
  pricing_records, cost = phelper.calculate_price(consts.SERVICE_DYNAMODB, iopsDb, query, pdim.writeCapacityUnitHours, pricing_records, cost)

  #DB Storage (TODO)

  #Data Transfer (TODO)
  #there is no additional charge for data transferred between Amazon DynamoDB and other Amazon Web Services within the same Region
  #data transferred across Regions (e.g., between Amazon DynamoDB in the US East (Northern Virginia) Region and Amazon EC2 in the EU (Ireland) Region), will be charged on both sides of the transfer.

  #API Requests (only applies for DDB Streams)(TODO)
  extraargs = {'priceDimensions':pdim}
  pricing_result = PricingResult(awsPriceListApiVersion, pdim.region, cost, pricing_records, **extraargs)
  log.debug(json.dumps(vars(pricing_result),sort_keys=False,indent=4))

  log.debug("Total time to compute: [{}]".format(ts.finish('totalCalculationDynamoDB')))
  return pricing_result.__dict__
