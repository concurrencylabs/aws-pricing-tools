
import json
import logging
from ..common import consts, phelper
from ..common.models import PricingResult
import tinydb

log = logging.getLogger()


def calculate(pdim):

  log.info("Calculating DynamoDB pricing with the following inputs: {}".format(str(pdim.__dict__)))

  ts = phelper.Timestamp()
  ts.start('totalCalculationKinesis')

  dbs, indexMetadata = phelper.loadDBs(consts.SERVICE_KINESIS, phelper.get_partition_keys(pdim.region,consts.SCRIPT_TERM_TYPE_ON_DEMAND))

  cost = 0
  pricing_records = []

  awsPriceListApiVersion = indexMetadata['Version']
  priceQuery = tinydb.Query()

  kinesisDb = dbs[phelper.create_file_key([consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_KINESIS_STREAMS])]

  #Shard Hours
  query = ((priceQuery['Group'] == 'Provisioned shard hour'))
  pricing_records, cost = phelper.calculate_price(consts.SERVICE_KINESIS, kinesisDb, query, pdim.shardHours, pricing_records, cost)

  #PUT Payload Units
  query = ((priceQuery['Group'] == 'Payload Units'))
  pricing_records, cost = phelper.calculate_price(consts.SERVICE_KINESIS, kinesisDb, query, pdim.putPayloadUnits, pricing_records, cost)

  #Extended Retention Hours
  query = ((priceQuery['Group'] == 'Addon shard hour'))
  pricing_records, cost = phelper.calculate_price(consts.SERVICE_KINESIS, kinesisDb, query, pdim.extendedDataRetentionHours, pricing_records, cost)

  #TODO: add Enhanced (shard-level) metrics

  #Data Transfer - N/A
  #Note there is no charge for data transfer in Kinesis as per https://aws.amazon.com/kinesis/streams/pricing/
  extraargs = {'priceDimensions':pdim}
  pricing_result = PricingResult(awsPriceListApiVersion, pdim.region, cost, pricing_records, **extraargs)
  log.debug(json.dumps(vars(pricing_result),sort_keys=False,indent=4))

  log.debug("Total time to compute: [{}]".format(ts.finish('totalCalculationKinesis')))
  return pricing_result.__dict__
