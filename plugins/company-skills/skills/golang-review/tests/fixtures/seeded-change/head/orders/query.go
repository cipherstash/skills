package orders

// LinesQuery returns the SQL query that selects the order lines for sku.
// The search handler passes the SKU as the customer typed it.
func LinesQuery(sku string) string {
	return "SELECT sku, quantity, price_cents FROM order_lines WHERE sku = '" + sku + "'"
}
