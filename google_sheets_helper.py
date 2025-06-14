# google_sheets_helper.py

def append_expense_row(sheet, row_data):
    try:
        sheet.append_row(row_data, value_input_option="USER_ENTERED")
    except Exception as e:
        print("❌ Error appending to sheet:", e)
