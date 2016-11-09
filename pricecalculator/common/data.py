import consts



class ElbPriceDimension():
    def __init__(self, hours, dataProcessedGb):
        self.hours = hours
        self.dataProcessedGb = dataProcessedGb

class Ec2PriceDimension():
    def __init__(self, hours, instance_type):
        self.hours = hours
        self.instanceType = instance_type


class RdsPriceDimension():
    def __init__(self, hours, instance_type, storage_gb_month, io_rate, backup_storage_gb_month,data_transfer_out_internet,data_transfer_out_inter_region_gb ):
        self.hours = hours
        self.instanceType = instance_type
        self.storageGbMonth = storage_gb_month
        self.ioRate = io_rate
        self.backupStorageDbMonth = backup_storage_gb_month
        self.dataTransferOutInternetGb = data_transfer_out_internet
        self.dataTransferOutInterRegionGb = data_transfer_out_inter_region_gb






"""
This object represents the total price calculation.
It includes an array of PricingRecord objects, which are a breakdown of how the price is calculated
"""
class PricingResult():
    def __init__(self, awsPriceListApiVersion, region, total_cost, pricing_records):
        total_cost = round(total_cost,2)
        self.version = "v1.0"
        self.awsPriceListApiVersion = awsPriceListApiVersion
        self.region = region
        self.totalCost = total_cost
        self.currency = consts.DEFAULT_CURRENCY
        self.pricingRecords = pricing_records

class PricingRecord():
    def __init__(self, service, amt, desc, pricePerUnit, usgUnits, rateCode):
        usgUnits = round(float(usgUnits),2)
        amt = round(amt,2)
        self.service = service
        #self.resourceId = resourceId  #leaving for future use
        #self.periodStart = start
        #self.periodEnd = end
        self.amount = amt
        self.description = desc
        self.pricePerUnit = pricePerUnit
        self.usageUnits = usgUnits
        self.rateCode = rateCode


#Desired JSON output returned by the funcion

"""
  {
    "version:"v1.0",
    "awsPriceListApiVersion":"20160812001705"
    "region":"us-east-1",
    "currency":"USD",
    "pricingRecords":[{
      "service":"elb",
      "amount":"12.33",
      "description":"$0.013 per On Demand Linux t2.micro Instance Hour",
      "pricePerUnit":"0.013",
      "usageUnits":"720",
      "rateCode":"HZC9FAP4F9Y8JW67.JRTCKXETXF.6YS6EN2CT7"
      }
    ]




  }

"""

