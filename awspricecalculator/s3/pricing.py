import json
import logging
from ..common import consts, phelper
from ..common.models import PricingResult
import tinydb



log = logging.getLogger()

def calculate(pdim):
  ts = phelper.Timestamp()
  ts.start('totalS3Calculation')

  log.info("Calculating S3 pricing with the following inputs: {}".format(str(pdim.__dict__)))

  dbs, indexMetadata = phelper.loadDBs(consts.SERVICE_S3, phelper.get_partition_keys(pdim.region, consts.SCRIPT_TERM_TYPE_ON_DEMAND))

  cost = 0
  pricing_records = []

  awsPriceListApiVersion = indexMetadata['Version']
  priceQuery = tinydb.Query()


  #Storage
  if pdim.storageSizeGb:
    storageDb = dbs[phelper.create_file_key([consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_STORAGE])]
    query = ((priceQuery['Storage Class'] == consts.S3_STORAGE_CLASS_MAP[pdim.storageClass]) &
             (priceQuery['Volume Type'] == consts.S3_VOLUME_TYPE_DICT[pdim.storageClass]))

    pricing_records, cost = phelper.calculate_price(consts.SERVICE_S3, storageDb, query, pdim.storageSizeGb, pricing_records, cost)

  #Data Transfer
  if pdim.dataTransferOutInternetGb:
    transferDb = dbs[phelper.create_file_key([consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_DATA_TRANSFER])]

    #Out to the internet
    query = ((priceQuery['To Location'] == 'External') & (priceQuery['Transfer Type'] == 'AWS Outbound'))
    pricing_records, cost = phelper.calculate_price(consts.SERVICE_S3, transferDb, query, pdim.dataTransferOutInternetGb, pricing_records, cost)
    #TODO: Intra region (regular and accelerated)
    #TODO: Out to the internet (Accelerated transfer)

  #TODO: Fee

  #API Request
  if pdim.requestNumber:
    requestDb = dbs[phelper.create_file_key([consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_API_REQUEST])]
    group = ''
    if pdim.storageClass == consts.SCRIPT_STORAGE_CLASS_STANDARD:
      if pdim.requestType in ['PUT','COPY','POST','LIST']: group=consts.S3_USAGE_GROUP_REQUESTS_TIER_1
      if pdim.requestType in ['GET']: group=consts.S3_USAGE_GROUP_REQUESTS_TIER_2
    if pdim.storageClass == consts.SCRIPT_STORAGE_CLASS_INFREQUENT_ACCESS:
      if pdim.requestType in ['PUT','COPY','POST','LIST']: group=consts.S3_USAGE_GROUP_REQUESTS_SIA_TIER1
      if pdim.requestType in ['GET']: group=consts.S3_USAGE_GROUP_REQUESTS_SIA_TIER2

    query = ((priceQuery['Group'] == group))
    pricing_records, cost = phelper.calculate_price(consts.SERVICE_S3, requestDb, query, pdim.requestNumber, pricing_records, cost)

  #Data Retrieval-SIA
  if pdim.dataRetrievalGb and pdim.storageClass == consts.SCRIPT_STORAGE_CLASS_INFREQUENT_ACCESS:
    requestDb = dbs[phelper.create_file_key([consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_API_REQUEST])]
    query = ((priceQuery['Group'] == consts.S3_USAGE_GROUP_REQUESTS_SIA_RETRIEVAL))
    pricing_records, cost = phelper.calculate_price(consts.SERVICE_S3, requestDb, query, pdim.dataRetrievalGb, pricing_records, cost)



  #TODO:Glacier (Bulk, Expedited, Glacier Requests


  pricing_result = PricingResult(awsPriceListApiVersion, pdim.region, cost, pricing_records)
  log.debug(json.dumps(vars(pricing_result),sort_keys=False,indent=4))

  print "Total time to compute S3 pricing: [{}]".format(ts.finish('totalS3Calculation'))
  return pricing_result.__dict__




