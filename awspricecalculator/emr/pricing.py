
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
    #The EMR component in the calculation always uses OnDemand (Reserved it's not supported yet for EMR)
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





  log.debug("regiondbs:[{}]".format(regiondbs.keys()))
  awsPriceListApiVersion = indexMetadata['Version']
  extraargs = {'priceDimensions':pdim}
  pricing_result = PricingResult(awsPriceListApiVersion, pdim.region, cost, pricing_records, **extraargs)
  log.debug(json.dumps(vars(pricing_result),sort_keys=False,indent=4))

  #proc = psutil.Process()
  #log.debug("open_files: {}".format(proc.open_files()))

  log.debug("Total time: [{}]".format(ts.finish('totalCalculation')))
  return pricing_result.__dict__
