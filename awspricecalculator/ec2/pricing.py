
import json
import logging
from ..common import consts, phelper
from ..common.models import PricingResult

import tinydb

log = logging.getLogger()


def calculate(pdim):

  log.info("Calculating EC2 pricing with the following inputs: {}".format(str(pdim.__dict__)))

  ts = phelper.Timestamp()
  ts.start('totalCalculation')
  ts.start('tinyDbLoadOnDemand')
  ts.start('tinyDbLoadReserved')

  awsPriceListApiVersion = ''
  cost = 0
  pricing_records = []
  priceQuery = tinydb.Query()

  #_/_/_/_/_/ ON-DEMAND PRICING _/_/_/_/_/
  if pdim.termType == consts.SCRIPT_TERM_TYPE_ON_DEMAND:
    #Load On-Demand DBs
    dbs, indexMetadata = phelper.loadDBs(consts.SERVICE_EC2, phelper.get_partition_keys(pdim.region, consts.SCRIPT_TERM_TYPE_ON_DEMAND))
    ts.finish('tinyDbLoadOnDemand')
    log.debug("Time to load OnDemand DB files: [{}]".format(ts.elapsed('tinyDbLoadOnDemand')))

    #cost = 0
    #pricing_records = []

    #awsPriceListApiVersion = indexMetadata['Version']

    #priceQuery = tinydb.Query()

    #TODO: Move common operations to a common module, and leave only EC2-specific operations in ec2/pricing.py (create a class)
    #Compute Instance
    if pdim.instanceHours:

      #computeDb = dbs[phelper.create_file_key(consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_COMPUTE_INSTANCE)]
      computeDb = dbs[phelper.create_file_key((consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_COMPUTE_INSTANCE))]
      ts.start('tinyDbSearchComputeFile')
      #purchaseOption = ''
      #if pdim.offeringType in consts.EC2_PURCHASE_OPTION_MAP:
      #  purchaseOption = consts.EC2_PURCHASE_OPTION_MAP[pdim.offeringType]
      query = ((priceQuery['Instance Type'] == pdim.instanceType) &
              (priceQuery['Operating System'] == consts.EC2_OPERATING_SYSTEMS_MAP[pdim.operatingSystem]) &
              (priceQuery['Tenancy'] == consts.EC2_TENANCY_SHARED) &
              (priceQuery['Pre Installed S/W'] == pdim.preInstalledSoftware) &
              (priceQuery['License Model'] == consts.EC2_LICENSE_MODEL_MAP[pdim.licenseModel]))# &
              #(priceQuery['OfferingClass'] == pdim.offeringClass) &
              #(priceQuery['PurchaseOption'] == purchaseOption ))

      pricing_records, cost = phelper.calculate_price(consts.SERVICE_EC2, computeDb, query, pdim.instanceHours, pricing_records, cost)
      log.debug("Time to search compute:[{}]".format(ts.finish('tinyDbSearchComputeFile')))

    #Data Transfer
    #dataTransferDb = dbs[phelper.create_file_key(consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_DATA_TRANSFER)]
    dataTransferDb = dbs[phelper.create_file_key((consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_DATA_TRANSFER))]

    #Out to the Internet
    if pdim.dataTransferOutInternetGb:
      ts.start('searchDataTransfer')
      query = ((priceQuery['To Location'] == 'External') & (priceQuery['Transfer Type'] == 'AWS Outbound'))
      pricing_records, cost = phelper.calculate_price(consts.SERVICE_EC2, dataTransferDb, query, pdim.dataTransferOutInternetGb, pricing_records, cost)
      log.debug("Time to search EC2 data transfer Out: [{}]".format(ts.finish('searchDataTransfer')))

    #Intra-regional data transfer - in/out/between EC2 AZs or using EIPs or ELB
    if pdim.dataTransferOutIntraRegionGb:
      query = ((priceQuery['Transfer Type'] == 'IntraRegion'))
      pricing_records, cost = phelper.calculate_price(consts.SERVICE_EC2, dataTransferDb, query, pdim.dataTransferOutIntraRegionGb, pricing_records, cost)

    #Inter-regional data transfer - out to other AWS regions
    if pdim.dataTransferOutInterRegionGb:
      query = ((priceQuery['Transfer Type'] == 'InterRegion Outbound') & (priceQuery['To Location'] == consts.REGION_MAP[pdim.toRegion]))
      pricing_records, cost = phelper.calculate_price(consts.SERVICE_EC2, dataTransferDb, query, pdim.dataTransferOutInterRegionGb, pricing_records, cost)

    #EBS Storage
    if pdim.ebsStorageGbMonth:
      #storageDb = dbs[phelper.create_file_key(consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_STORAGE)]
      storageDb = dbs[phelper.create_file_key((consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_STORAGE))]
      query = ((priceQuery['Volume Type'] == pdim.volumeType))
      pricing_records, cost = phelper.calculate_price(consts.SERVICE_EBS, storageDb, query, pdim.ebsStorageGbMonth, pricing_records, cost)


    #System Operation (pIOPS)
    if pdim.volumeType == consts.EBS_VOLUME_TYPE_PIOPS and pdim.pIops:
      #storageDb = dbs[phelper.create_file_key(consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_SYSTEM_OPERATION)]
      storageDb = dbs[phelper.create_file_key((consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_SYSTEM_OPERATION))]
      query = ((priceQuery['Group'] == 'EBS IOPS'))
      pricing_records, cost = phelper.calculate_price(consts.SERVICE_EBS, storageDb, query, pdim.pIops, pricing_records, cost)

    #Snapshot Storage
    if pdim.ebsSnapshotGbMonth:
      #snapshotDb = dbs[phelper.create_file_key(consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_SNAPSHOT)]
      snapshotDb = dbs[phelper.create_file_key((consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_SNAPSHOT))]
      query = ((priceQuery['usageType'] == consts.REGION_PREFIX_MAP[pdim.region]+'EBS:SnapshotUsage'))#EBS:SnapshotUsage comes with a prefix in the PriceList API file (i.e. EU-EBS:SnapshotUsage)
      pricing_records, cost = phelper.calculate_price(consts.SERVICE_EBS, snapshotDb, query, pdim.ebsSnapshotGbMonth, pricing_records, cost)

    #Load Balancer
    if pdim.elbHours:
      #elbDb = dbs[phelper.create_file_key(consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_LOAD_BALANCER)]
      elbDb = dbs[phelper.create_file_key((consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_LOAD_BALANCER))]
      #TODO:Add support for LoadBalancing:Application
      query = ((priceQuery['usageType'] == consts.REGION_PREFIX_MAP[pdim.region]+'LoadBalancerUsage') & (priceQuery['operation'] == 'LoadBalancing'))
      pricing_records, cost = phelper.calculate_price(consts.SERVICE_ELB, elbDb, query, pdim.elbHours, pricing_records, cost)

    if pdim.elbDataProcessedGb:
      #elbDb = dbs[phelper.create_file_key(consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_LOAD_BALANCER)]
      elbDb = dbs[phelper.create_file_key((consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_LOAD_BALANCER))]
      query = ((priceQuery['usageType'] == consts.REGION_PREFIX_MAP[pdim.region]+'DataProcessing-Bytes') & (priceQuery['operation'] == 'LoadBalancing'))
      pricing_records, cost = phelper.calculate_price(consts.SERVICE_ELB, elbDb, query, pdim.elbDataProcessedGb, pricing_records, cost)

    #TODO: EIP
    #TODO: Dedicated Host
    #TODO: NAT Gateway
    #TODO: Fee
    #TODO: Reserved


  #_/_/_/_/_/ RESERVED PRICING _/_/_/_/_/
  #Load Reserved DBs
  if pdim.termType == consts.SCRIPT_TERM_TYPE_RESERVED:
    #dbs, indexMetadata = phelper.loadDBs(consts.SERVICE_EC2, phelper.get_partition_keys(pdim.region, consts.SCRIPT_TERM_TYPE_RESERVED))
    indexArgs = {'offeringClasses':[consts.EC2_OFFERING_CLASS_MAP[pdim.offeringClass]],
                 'tenancies':[consts.EC2_TENANCY_MAP[pdim.tenancy]], 'purchaseOptions':[consts.EC2_PURCHASE_OPTION_MAP[pdim.offeringType]]}
    dbs, indexMetadata = phelper.loadDBs(consts.SERVICE_EC2, phelper.get_partition_keys(pdim.region, consts.SCRIPT_TERM_TYPE_RESERVED, **indexArgs))
    ts.finish('tinyDbLoadReserved')
    log.debug("Time to load Reserved DB files: [{}]".format(ts.elapsed('tinyDbLoadReserved')))


    #computeDb = dbs[phelper.create_file_key(consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType], consts.PRODUCT_FAMILY_COMPUTE_INSTANCE)]
    computeDb = dbs[phelper.create_file_key((consts.REGION_MAP[pdim.region], consts.TERM_TYPE_MAP[pdim.termType],
                                             consts.PRODUCT_FAMILY_COMPUTE_INSTANCE, consts.EC2_OFFERING_CLASS_STANDARD,
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
      pricing_records, cost = phelper.calculate_price(consts.SERVICE_EC2, computeDb, hrsQuery, pdim.instanceHours, pricing_records, cost)


      log.debug("Time to search:[{}]".format(ts.finish('tinyDbSearchComputeFileReserved')))



  awsPriceListApiVersion = indexMetadata['Version']
  pricing_result = PricingResult(awsPriceListApiVersion, pdim.region, cost, pricing_records)
  log.debug(json.dumps(vars(pricing_result),sort_keys=False,indent=4))

  log.debug("Total time: [{}]".format(ts.finish('totalCalculation')))
  return pricing_result.__dict__
