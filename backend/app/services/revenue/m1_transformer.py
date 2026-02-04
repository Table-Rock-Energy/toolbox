"""Transform parsed revenue data to M1 Upload format."""


from app.models.revenue import M1UploadRow, RevenueRow, RevenueStatement
from app.utils.helpers import generate_uid, map_interest_type, map_product_code, map_tax_type


def transform_to_m1(statements: list[RevenueStatement]) -> list[M1UploadRow]:
    """Transform a list of revenue statements to M1 Upload format rows."""
    m1_rows = []
    line_number = 1

    for statement in statements:
        for row in statement.rows:
            m1_row = transform_row(statement, row, line_number)
            m1_rows.append(m1_row)
            line_number += 1

    return m1_rows


def transform_row(
    statement: RevenueStatement,
    row: RevenueRow,
    line_number: int
) -> M1UploadRow:
    """Transform a single revenue row to M1 Upload format."""
    # Generate UID
    uid = generate_uid(
        statement.check_number or "",
        row.property_number or "",
        line_number
    )

    # Format check date
    check_date_str = ""
    if statement.check_date:
        check_date_str = statement.check_date.strftime("%m/%d/%Y")

    # Format sales date
    sales_date_str = ""
    if row.sales_date:
        sales_date_str = row.sales_date.strftime("%m/%d/%Y")

    # Format check amount
    check_amount_str = ""
    if statement.check_amount:
        check_amount_str = f"{statement.check_amount:.2f}"

    # Format decimal values
    def format_decimal(value, precision: int = 2) -> str:
        if value is None:
            return ""
        return f"{value:.{precision}f}"

    def format_interest(value) -> str:
        if value is None:
            return ""
        # Interests typically have more decimal places
        return f"{value:.8f}"

    # Map product code
    product_code = row.product_code or ""
    product_desc = map_product_code(product_code)

    # Map interest type
    interest_type = ""
    if row.interest_type:
        interest_type = map_interest_type(row.interest_type)

    # Map tax type
    tax_type = ""
    if row.tax_type:
        tax_type = map_tax_type(row.tax_type)

    m1_row = M1UploadRow(
        uid=uid,
        payor=statement.payor or "",
        check_number=statement.check_number or "",
        check_amount=check_amount_str,
        check_date=check_date_str,
        m1_property_id="",  # To be filled by user/system
        payor_prop_number=row.property_number or "",
        operator_prop_number=row.property_number or "",
        accounting_ref_id="",
        property_name=row.property_name or "",
        operator_name=statement.operator_name or "",
        owner_number=statement.owner_number or "",
        owner_name=statement.owner_name or "",
        sales_date=sales_date_str,
        product_code=product_code,
        property_description=row.product_description or product_desc,
        decimal_interest=format_interest(row.decimal_interest),
        interest_type=interest_type,
        avg_price=format_decimal(row.avg_price, 4),
        property_gross_volume=format_decimal(row.property_gross_volume, 2),
        property_gross_revenue=format_decimal(row.property_gross_revenue, 2),
        owner_volume=format_decimal(row.owner_volume, 2),
        owner_value=format_decimal(row.owner_value, 2),
        owner_tax_amount=format_decimal(row.owner_tax_amount, 2),
        tax_type=tax_type,
        owner_deduct_amount=format_decimal(row.owner_deduct_amount, 2),
        deduct_code=row.deduct_code or "",
        owner_net_revenue=format_decimal(row.owner_net_revenue, 2),
        line_number=str(line_number),
    )

    return m1_row


def validate_m1_row(row: M1UploadRow) -> list[str]:
    """Validate an M1 Upload row and return list of errors."""
    errors = []

    # Required fields
    if not row.uid:
        errors.append("Missing UID")

    # Numeric validation
    numeric_fields = [
        ("check_amount", row.check_amount),
        ("decimal_interest", row.decimal_interest),
        ("avg_price", row.avg_price),
        ("property_gross_volume", row.property_gross_volume),
        ("property_gross_revenue", row.property_gross_revenue),
        ("owner_volume", row.owner_volume),
        ("owner_value", row.owner_value),
        ("owner_tax_amount", row.owner_tax_amount),
        ("owner_deduct_amount", row.owner_deduct_amount),
        ("owner_net_revenue", row.owner_net_revenue),
    ]

    for field_name, field_value in numeric_fields:
        if field_value:
            try:
                float(field_value)
            except ValueError:
                errors.append(f"Invalid numeric value for {field_name}: {field_value}")

    return errors


def get_m1_row_as_dict(row: M1UploadRow) -> dict:
    """Convert M1UploadRow to dictionary for CSV export."""
    return {
        "UID": row.uid,
        "Payor": row.payor,
        "Check Number": row.check_number,
        "Check Amount": row.check_amount,
        "Check Date": row.check_date,
        "M1 Property ID": row.m1_property_id,
        "Payor Prop #": row.payor_prop_number,
        "Operator Prop #": row.operator_prop_number,
        "Accounting Ref ID": row.accounting_ref_id,
        "Property Name": row.property_name,
        "Operator Name": row.operator_name,
        "Owner Number": row.owner_number,
        "Owner Name": row.owner_name,
        "Sales Date": row.sales_date,
        "Product Code": row.product_code,
        "Property Description": row.property_description,
        "Decimal Interest": row.decimal_interest,
        "Interest Type": row.interest_type,
        "Avg Price": row.avg_price,
        "Property Gross Volume": row.property_gross_volume,
        "Property Gross Revenue": row.property_gross_revenue,
        "Owner Volume": row.owner_volume,
        "Owner Value": row.owner_value,
        "Owner Tax Amount": row.owner_tax_amount,
        "Tax Type": row.tax_type,
        "Owner Deduct Amount": row.owner_deduct_amount,
        "Deduct Code": row.deduct_code,
        "Owner Net Revenue": row.owner_net_revenue,
        "Line Number": row.line_number,
    }
