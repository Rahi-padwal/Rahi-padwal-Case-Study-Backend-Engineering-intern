@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.json

    # 1. Validate required fields
    required_fields = ['name', 'sku', 'price', 'warehouse_id', 'initial_quantity']
    for field in required_fields:
        if field not in data:
            return {"error": f"Missing required field: {field}"}, 400

    # 2. Validate types
    try:
        price = float(data['price'])
        initial_quantity = int(data['initial_quantity'])
        warehouse_id = int(data['warehouse_id'])
    except (ValueError, TypeError):
        return {"error": "Invalid data types for price, quantity, or warehouse_id"}, 400

    if price < 0 or initial_quantity < 0:
        return {"error": "Price and quantity must be non-negative"}, 400

    try:
        product = Product(
            name=data['name'],
            sku=data['sku'],
            price=price,
            warehouse_id=warehouse_id
        )
        db.session.add(product)
        db.session.flush()  # gets product.id without committing yet

        inventory = Inventory(
            product_id=product.id,
            warehouse_id=warehouse_id,
            quantity=initial_quantity
        )
        db.session.add(inventory)

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        return {"error": "Failed to create product", "details": str(e)}, 500

    return {"message": "Product created", "product_id": product.id}, 201
