import consts
from errors import ValidationError



class ElbPriceDimension():
    def __init__(self, hours, dataProcessedGb):
        self.hours = hours
        self.dataProcessedGb = dataProcessedGb

class Ec2PriceDimension():
    def __init__(self, hours, instance_type):
        self.hours = hours
        self.instanceType = instance_type


class RdsPriceDimension():
    def __init__(self, hours, instance_type, storage_gb_month, io_rate, backup_storage_gb_month,
                 data_transfer_out_internet,data_transfer_out_inter_region_gb ):
        self.hours = hours
        self.instanceType = instance_type
        self.storageGbMonth = storage_gb_month
        self.ioRate = io_rate
        self.backupStorageDbMonth = backup_storage_gb_month
        self.dataTransferOutInternetGb = data_transfer_out_internet
        self.dataTransferOutInterRegionGb = data_transfer_out_inter_region_gb


class LambdaPriceDimension():
    def __init__(self,region, request_count, avg_duration_ms, memory_mb,  data_tranfer_out_internet_gb,
                 data_transfer_out_intra_region_gb, data_transfer_out_inter_region_gb, to_region):
        self.region = region
        self.requestCount = request_count
        self.avgDurationMs = avg_duration_ms
        self.memoryMb = memory_mb
        self.dataTransferOutInternetGb = data_tranfer_out_internet_gb
        self.dataTransferOutIntraRegionGb = data_transfer_out_intra_region_gb
        self.dataTransferOutInterRegionGb = data_transfer_out_inter_region_gb
        self.toRegion = to_region
        self.validate()

    def validate(self):
        validation_ok = True
        validation_message = ""
        if not self.region:
            validation_message = "Region must be specified"
            validation_ok = False
        if self.region not in consts.SUPPORTED_REGIONS:
            validation_message = "Region must be one of the following:"+str(consts.SUPPORTED_REGIONS)
            validation_ok = False
        if self.requestCount == 0 and (self.avgDurationMs > 0 or self.memoryMb > 0):
            validation_message = "Cannot have value for average duration or memory if requestCount is zero"
            validation_ok = False
        if self.dataTransferOutInterRegionGb > 0 and not self.toRegion:
            validation_message = "Must specify a to-region if you specify data-transfer-out-interregion_gb"
            validation_ok = False
        if not validation_ok:
            raise ValidationError(validation_message)

        return






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
        self.usageUnits = int(usgUnits)
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

