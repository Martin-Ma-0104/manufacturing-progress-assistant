"""Versioned PREPARATION contracts, not a business-data importer or predictor."""
from copy import deepcopy
import json

VERSION='1.0'
# Field name, expected type/unit, relation or meaning. No invented example values.
ENTITIES={
 'shift_runtime': [('production_date','date','business date'),('machine_id','text','reviewed machine ID'),
   ('shift','Day|Night','explicit business shift'),('product_spec','text','SKU, width and roll length'),
   ('planned_available_hours','hours','calendar-backed planned availability'),('actual_run_minutes','minutes','measured run time, not shift duration'),
   ('qualified_quantity','number + uom','observed output with explicit unit'),('setup_minutes','minutes','measured changeover time')],
 'rate_standards': [('machine_id','text','machine capability'),('product_spec','text','exact matching specification'),
   ('rate','quantity/hour','standard rate; explicit output unit'),('basis','text','validated source and effective date')],
 'routing_wip': [('product_spec','text','exact specification'),('operation_id','text','operation and predecessor'),
   ('observed_at','local datetime + timezone','observation timestamp'),('queued_quantity','number + uom','WIP before operation'),
   ('wait_minutes','minutes','observed waiting; needed for bottleneck evidence')],
 'order_lines': [('order_line_id','text','unique order line'),('product_spec','text','SKU, width and roll length'),
   ('required_quantity','number + uom','required qualified output'),('due_date','date','promised date; not estimated')],
 'production_allocations': [('production_record_key','text','reviewed production date/shift/machine/product'),
   ('order_line_id','text','references order_lines'),('allocated_qualified_quantity','number + uom','sum allocated cannot exceed qualified output')],
 'inventory_movements': [('movement_id','text','unique immutable transaction'),('material_id','text','canonical material'),
   ('recorded_at','local datetime + timezone','as-of timestamp'),('quantity_change','signed number + uom','receipt or issue; traceable starting balance'),
   ('reserved_quantity','number + uom','reserved amount, not available stock'),('expected_receipts','quantity + uom + due date','confirmed inbound supply')],
 'inventory_balances': [('material_id','text','canonical material'),('as_of','local datetime + timezone','stock snapshot time'),
   ('quantity_on_hand','number + uom','verified physical/book balance'),('quantity_reserved','number + uom','committed stock, not available')],
 'inbound_receipts': [('receipt_id','text','unique confirmed inbound line'),('material_id','text','canonical material'),
   ('expected_quantity','number + uom','confirmed quantity'),('expected_date','date','expected receipt date')],
 'product_bom': [('product_spec','text','exact output specification'),('material_id','text','references inventory material'),
   ('quantity_per_output','material uom/output uom','explicit conversion with effective date')],
}
MODULES={
 '产能与情景排程': ['shift_runtime','rate_standards','routing_wip'],
 '订单进度与交期': ['order_lines','production_allocations','shift_runtime','rate_standards'],
 '库存与缺料': ['inventory_movements','inventory_balances','inbound_receipts','product_bom','order_lines'],
}


def blueprint():
    return dict(version=VERSION,purpose='Field preparation only; not accepted by the production JSON importer.',
        modules={name:dict(status='awaiting_real_data',required_entities=entities) for name,entities in MODULES.items()},
        entities={name:dict(fields=[dict(name=n,type_and_unit=t,meaning=m) for n,t,m in fields],records=[])
                  for name,fields in ENTITIES.items()},
        rules=['Do not mix simulated enterprise records with reviewed production.',
               'Do not infer a permanent 2000 m roll length from a batch-specific confirmation.',
               'Allocations must not double count qualified output across orders.',
               'Missing units or unit conversions block calculations.',
               'No business schema migration or real-data import is enabled in this version.'])


def readiness():
    return [dict(module=name,status='待接入真实数据',missing_entities=deepcopy(entities),
                 calculation_enabled=False) for name,entities in MODULES.items()]


def template_bytes():
    return (json.dumps(blueprint(),ensure_ascii=False,indent=2)+'\n').encode('utf-8')
