import json
import logging
import os, sys
from ..common import consts, phelper
from ..common.errors import ValidationError
from ..common.data import PricingResult, PricingRecord

log = logging.getLogger()


def calculate(pdim):

  log.info("Calculating Lambda pricing with the following inputs: {}".format(str(pdim.__dict__)))

  __location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
  index_file = open(os.path.join(__location__, 'index.json')).read();
  price_data = json.loads(index_file)
  awsPriceListApiVersion = price_data['version']

  #usage_types = phelper.get_distinct_product_attributes(price_data, 'usagetype', region=pdim.region)
  #print "usage_types: [{}]".format(usage_types)

  cost = 0
  pricing_records = []
  skus = phelper.get_skus(price_data, region=pdim.region)

  for sku in skus:
    service = consts.SERVICE_LAMBDA

    sku_data = price_data['products'][sku]
    term_data = phelper.get_terms(price_data, [sku], type='OnDemand')
    pd = phelper.get_price_dimensions(term_data)

    for p in pd:
      amt = 0
      usageUnits = 0
      billableBand = 0
      pricePerUnit = 0

      pricePerUnit = float(p['pricePerUnit']['USD'])

      #TODO:calculate free-tier (include a flag)
      if sku_data['productFamily'] == consts.PRODUCT_FAMILY_SERVERLESS:
        #Requests
        if sku_data['attributes']['group'] == 'AWS-Lambda-Requests':
          usageUnits = pdim.requestCount
        #GB-s (aka compute time)
        if sku_data['attributes']['group'] == 'AWS-Lambda-Duration':
          usageUnits = pdim.requestCount * (float(pdim.avgDurationMs) / 1000) * (float(pdim.memoryMb) / 1024)

        amt = pricePerUnit * float(usageUnits)

      #Data Transfer
      if sku_data['productFamily'] == consts.PRODUCT_FAMILY_DATA_TRANSFER:
        billableBand = 0
        #To internet            
        if pdim.dataTransferOutInternetGb and phelper.is_data_transfer_out_internet(sku_data):
          billableBand = phelper.getBillableBand(p, pdim.dataTransferOutInternetGb)
          amt = pricePerUnit * billableBand

        #Intra-regional data transfer - in/out/between EC2 AZs or using IPs or ELB
        if pdim.dataTransferOutIntraRegionGb and phelper.is_data_transfer_intraregional(sku_data):
          usageUnits = pdim.dataTransferOutIntraRegionGb
          amt = pricePerUnit * usageUnits

        #Inter-regional data transfer - out to other AWS regions
        if pdim.dataTransferOutInterRegionGb and phelper.is_data_transfer_interregional(sku_data, pdim.toRegion):
          usageUnits = pdim.dataTransferOutInterRegionGb
          amt = pricePerUnit * usageUnits


      if amt > 0:
        cost = cost + amt
        if billableBand > 0: usageUnits = billableBand
        pricing_record = PricingRecord(service,round(amt,4),p['description'],pricePerUnit,usageUnits,p['rateCode'])
        pricing_records.append(vars(pricing_record))

  pricing_result = PricingResult(awsPriceListApiVersion, pdim.region, cost, pricing_records)
  return pricing_result.__dict__


