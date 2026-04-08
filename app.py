from flask import jsonify
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import joinedload

@app.route('/api/companies/<int:company_id>/alerts/low-stock', methods=['GET'])
def low_stock_alerts(company_id):

    if not Company.query.get(company_id):
        return jsonify({"error": "Company not found"}), 404

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    # Aggregate sales per product/warehouse in last 30 days
    recent_sales = (
        db.session.query(
            InventoryLog.product_id,
            InventoryLog.warehouse_id,
            func.sum(func.abs(InventoryLog.change_qty)).label('total_sold')
        )
        .join(Warehouse, InventoryLog.warehouse_id == Warehouse.id)
        .filter(
            Warehouse.company_id == company_id,        # scoped to company directly
            InventoryLog.reason == 'sale',
            InventoryLog.created_at >= thirty_days_ago
        )
        .group_by(InventoryLog.product_id, InventoryLog.warehouse_id)
        .subquery()
    )

    # Single query: inventory + product + warehouse + sales, filtered to low stock
    results = (
        db.session.query(Inventory, Product, Warehouse, recent_sales.c.total_sold)
        .join(Product, Inventory.product_id == Product.id)
        .join(Warehouse, Inventory.warehouse_id == Warehouse.id)
        .join(recent_sales, (recent_sales.c.product_id == Inventory.product_id) &
                            (recent_sales.c.warehouse_id == Inventory.warehouse_id))
        .filter(
            Warehouse.company_id == company_id,
            Inventory.quantity < Product.low_stock_threshold
        )
        .options(joinedload(Product.suppliers))        # avoids N+1 supplier queries
        .all()
    )

    def build_alert(inventory, product, warehouse, total_sold):
        avg_daily = total_sold / 30.0
        supplier = next((s for s in product.suppliers if s.is_primary), 
                        next(iter(product.suppliers), None))
        return {
            "product_id": product.id,
            "product_name": product.name,
            "sku": product.sku,
            "warehouse_id": warehouse.id,
            "warehouse_name": warehouse.name,
            "current_stock": inventory.quantity,
            "threshold": product.low_stock_threshold,
            "days_until_stockout": int(inventory.quantity / avg_daily) if avg_daily else None,
            "supplier": {"id": supplier.id, "name": supplier.name, "contact_email": supplier.contact_email} if supplier else None
        }

    alerts = [build_alert(*row) for row in results]
    return jsonify({"alerts": alerts, "total_alerts": len(alerts)}), 200
