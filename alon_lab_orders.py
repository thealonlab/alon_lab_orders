import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import chardet
import gdown
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials
from io import BytesIO
import io


# Google Drive file ID of the uploaded SQLite database
GOOGLE_DRIVE_FILE_ID = "1wwnKYEPhtTb-59aGfkX5jQXmfbUKcXFK"
LOCAL_DB_FILE = "inventory.db"

# Load credentials from Streamlit secrets
credentials_info = st.secrets["google_drive"]
credentials_dict = {
    "type": credentials_info["type"],
    "project_id": credentials_info["project_id"],
    "private_key_id": credentials_info["private_key_id"],
    "private_key": credentials_info["private_key"].replace("\\n", "\n"),  # Handle multiline key
    "client_email": credentials_info["client_email"],
    "client_id": credentials_info["client_id"],
    "auth_uri": credentials_info["auth_uri"],
    "token_uri": credentials_info["token_uri"],
    "auth_provider_x509_cert_url": credentials_info["auth_provider_x509_cert_url"],
    "client_x509_cert_url": credentials_info["client_x509_cert_url"]
}

# Create credentials object for Google API

# Function to authenticate and create a Google Drive service client
def get_drive_service():
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=["https://www.googleapis.com/auth/drive"])
    service = build("drive", "v3", credentials=credentials)
    return service


# Function to download the database file from Google Drive
def download_db():
    if not os.path.exists(LOCAL_DB_FILE) or not validate_db():
        st.info("Downloading database from Google Drive...")
        try:
            gdown.cached_download(f"https://drive.google.com/uc?id={GOOGLE_DRIVE_FILE_ID}", LOCAL_DB_FILE, quiet=False)
            st.success("Database downloaded successfully.")
        except Exception as e:
            st.error(f"Failed to download the database: {e}")

# Function to check if the database contains required tables
def validate_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='inventory';")
        table_exists = cursor.fetchone()
        conn.close()
        return bool(table_exists)
    except sqlite3.Error:
        return False

# Function to upload the updated database file back to Google Drive

def upload_db():
    st.info("Uploading updated database to Google Drive...")
    try:
        service = get_drive_service()
        
        media = MediaFileUpload(LOCAL_DB_FILE, mimetype='application/x-sqlite3', resumable=True)
        
        service.files().update(
            fileId=GOOGLE_DRIVE_FILE_ID,
            media_body=media
        ).execute()

        st.success("Database uploaded successfully to Google Drive.")
    except Exception as e:
        st.error(f"Failed to upload the database: {e}")


#def upload_db():
#    st.info("Uploading updated database to Google Drive...")
#    try:
#        service = get_drive_service()
#
#        # Use MediaFileUpload for proper file upload
#        media = MediaFileUpload(LOCAL_DB_FILE, mimetype='application/octet-stream', resumable=True)
#
#        service.files().update(
#            fileId=GOOGLE_DRIVE_FILE_ID,
#            media_body=media
#        ).execute()
#
#        st.success("Database uploaded successfully to Google Drive.")
#    except Exception as e:
#        st.error(f"Failed to upload the database: {e}")


#ef upload_db():
#   st.info("Uploading updated database to Google Drive...")
#   try:
#       service = get_drive_service()
#       file_metadata = {"name": LOCAL_DB_FILE}
#       with open(LOCAL_DB_FILE, "rb") as media:
#           service.files().update(
#               fileId=GOOGLE_DRIVE_FILE_ID,
#               media_body=media
#           ).execute()
#       st.success("Database uploaded successfully to Google Drive.")
#   except Exception as e:
#       st.error(f"Failed to upload the database: {e}")

# Database connection
def get_db_connection():
    return sqlite3.connect(LOCAL_DB_FILE, check_same_thread=False)

## Database connection old
#def get_db_connection():
#    return sqlite3.connect("inventory.db")

# Initialize database
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requested_by TEXT NOT NULL,
            catalog_number TEXT NOT NULL,
            vendor TEXT NOT NULL,
            name TEXT NOT NULL,
            url TEXT,
            quantity INTEGER DEFAULT 1,
            unit TEXT,
            notes TEXT,
            cost REAL DEFAULT 0.0,
            status TEXT NOT NULL DEFAULT 'Requested',
            order_date TEXT,
            received_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Start by downloading the database and initializing it
download_db()
init_db()

# Function to retrieve inventory data
def get_inventory():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inventory")
    rows = cursor.fetchall()
    conn.close()
    return rows

inventory_df = pd.DataFrame(get_inventory(), columns=[
    "ID", "Requested By", "Catalog Number", "Vendor", "Name", "URL",
    "Quantity", "Unit", "Notes", "Cost", "Status", "Order Date", "Received Date"
])
inventory_df = inventory_df.drop(columns=["ID"])

# Function to add an item to the database
def add_inventory_item(requested_by, catalog_number, vendor, name, url, quantity, unit, notes, cost, status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO inventory (requested_by, catalog_number, vendor, name, url, quantity, unit, notes, cost, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (requested_by, catalog_number, vendor, name, url, quantity, unit, notes, cost, status))
    conn.commit()
    conn.close()
    upload_db()  # Upload the updated database after addition

# Function to delete an item from the database
def delete_inventory_item(catalog_number, vendor):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inventory WHERE catalog_number = ? AND vendor = ?", (catalog_number, vendor))
    conn.commit()
    conn.close()
    upload_db()  # Upload the updated database after addition

# Function to get an item by catalog number and vendor
def get_item_by_catalog_and_vendor(catalog_number, vendor):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM inventory 
        WHERE catalog_number = ? AND vendor = ?
    ''', (catalog_number, vendor))
    item = cursor.fetchone()
    conn.close()
    return item

# Function to edit an existing item
def edit_inventory_item(item_id, requested_by, catalog_number, vendor, name, url, quantity, unit, notes, cost, status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE inventory 
        SET requested_by = ?, catalog_number = ?, vendor = ?, name = ?, url = ?, quantity = ?, unit = ?, notes = ?, cost = ?, status = ?
        WHERE id = ?
    ''', (requested_by, catalog_number, vendor, name, url, quantity, unit, notes, cost, status, item_id))
    conn.commit()
    conn.close()
    upload_db()  # Upload the updated database after addition

# Function to detect file encoding
def detect_encoding(uploaded_file):
    raw_data = uploaded_file.read()
    result = chardet.detect(raw_data)
    encoding = result['encoding']
    uploaded_file.seek(0)
    return encoding

# Function to import CSV data into the database
def import_csv_to_db(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file, encoding='ISO-8859-1')

        # Standardizing column names
        df.columns = df.columns.str.strip().str.replace(" ", "_").str.lower()

        conn = get_db_connection()
        cursor = conn.cursor()

        required_columns = {"catalog_number", "vendor", "name"}
        if not required_columns.issubset(set(df.columns)):
            st.error(f"Missing required columns: {required_columns - set(df.columns)}")
            return

        # Normalize data for comparison
        df["catalog_number"] = df["catalog_number"].astype(str).str.strip().str.lower()
        df["vendor"] = df["vendor"].astype(str).str.strip().str.lower()

        # Retrieve existing items from database
        existing_items = pd.read_sql_query('SELECT catalog_number, vendor FROM inventory', conn)
        existing_items["catalog_number"] = existing_items["catalog_number"].astype(str).str.strip().str.lower()
        existing_items["vendor"] = existing_items["vendor"].astype(str).str.strip().str.lower()

        df.reset_index(drop=True, inplace=True)
        existing_items.reset_index(drop=True, inplace=True)

        new_entries_count = 0
        skipped_entries_count = 0

        for _, row in df.iterrows():
            catalog_number = row["catalog_number"].strip().lower()
            vendor = row["vendor"].strip().lower()

            is_duplicate = (
                (existing_items["catalog_number"] == catalog_number) &
                (existing_items["vendor"] == vendor)
            ).any()

            if is_duplicate:
                skipped_entries_count += 1
                continue

            cursor.execute('''
                INSERT INTO inventory (requested_by, catalog_number, vendor, name, url, quantity, unit, notes, cost, status, order_date, received_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                row.get("requested_by", "Unknown"),
                catalog_number,
                vendor,
                row.get("name", "Unknown Item"),
                row.get("url", ""),
                row.get("quantity", 1),
                row.get("unit", ""),
                row.get("notes", ""),
                row.get("cost", 0.0),
                row.get("status", "Requested"),
                row.get("order_date", None),
                row.get("received_date", None)
            ))

            new_entries_count += 1

        conn.commit()
        conn.close()

        st.success(f"CSV imported: {new_entries_count} new records, {skipped_entries_count} duplicates skipped.")
        st.rerun()

    except Exception as e:
        st.error(f"Error importing CSV: {e}")

# Function to handle duplicates by merging them
def purge_and_merge_duplicates():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Identify duplicates based on catalog number and vendor
    query = '''
        SELECT catalog_number, vendor, COUNT(*) as count
        FROM inventory
        GROUP BY catalog_number, vendor
        HAVING COUNT(*) > 1
    '''
    duplicates = cursor.execute(query).fetchall()

    if not duplicates:
        st.success("No duplicates found in the database.")
        conn.close()
        return

    for catalog_number, vendor, count in duplicates:
        # Fetch all duplicate rows
        cursor.execute('''
            SELECT * FROM inventory 
            WHERE catalog_number = ? AND vendor = ?
            ORDER BY order_date DESC, received_date DESC
        ''', (catalog_number, vendor))
        
        duplicate_rows = cursor.fetchall()

        if duplicate_rows:
            # Merge duplicate records
            total_quantity = sum(row[6] for row in duplicate_rows)  # Summing quantity
            combined_notes = " | ".join(filter(None, {row[8] for row in duplicate_rows}))  # Combine notes
            latest_order_date = max(filter(None, [row[10] for row in duplicate_rows])) if any(row[10] for row in duplicate_rows) else None
            latest_received_date = max(filter(None, [row[11] for row in duplicate_rows])) if any(row[11] for row in duplicate_rows) else None

            # Keep the first row and update it with merged values
            first_row = duplicate_rows[0]
            cursor.execute('''
                UPDATE inventory 
                SET quantity = ?, notes = ?, order_date = ?, received_date = ?
                WHERE id = ?
            ''', (total_quantity, combined_notes, latest_order_date, latest_received_date, first_row[0]))

            # Remove other duplicate rows
            for row in duplicate_rows[1:]:
                cursor.execute('DELETE FROM inventory WHERE id = ?', (row[0],))

    conn.commit()
    conn.close()
    st.success(f"Duplicates purged and merged successfully.")
    upload_db()  # Upload the updated database after addition


# Function to update item status
def update_inventory_item(catalog_number, vendor, new_name, new_status, new_quantity, new_requested_by, new_notes):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Reset order and received dates when status is set to Requested
    order_date = None if new_status == "Requested" else None
    received_date = None

    cursor.execute('''
        UPDATE inventory 
        SET name = ?, status = ?, quantity = ?, requested_by = ?, notes = ?, 
            order_date = ?, 
            received_date = ?
        WHERE catalog_number = ? AND vendor = ?
    ''', (new_name, new_status, new_quantity, new_requested_by, new_notes, order_date, received_date, catalog_number, vendor))

    conn.commit()
    conn.close()
    upload_db()  # Upload the updated database after addition

# Function to download CSV template
def download_csv_template():
    template_data = {
        "requested_by": ["Assaf Alon"],
        "catalog_number": ["12345"],
        "vendor": ["Sigma"],
        "name": ["Chemical A"],
        "url": ["http://example.com"],
        "quantity": [1],
        "unit": ["200/Case"],
        "notes": ["For research use"],
        "cost": [0.0],
        "status": ["Requested"],
        "order_date": [""],
        "received_date": [""]
    }

    df_template = pd.DataFrame(template_data)
    buffer = BytesIO()
    df_template.to_csv(buffer, index=False)
    buffer.seek(0)
    return buffer

# Streamlit UI

# Initialize session state variables if not already set
for key, default in {
    'catalog_number': "",
    'vendor': "",
    'name': "",
    'url': "",
    'quantity': 1,
    'unit': "",
    'notes': "",
    'cost': 0.0,
    'status': "Requested",
    'requested_by': "Assaf Alon"
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


st.title("Lab Inventory Management")


# Status filter
status_filter = st.selectbox(
    "Filter by status:",
    ["All"] + inventory_df["Status"].unique().tolist(),
    index=0
)

# Filter inventory based on selected status
if status_filter != "All":
    filtered_inventory_df = inventory_df[inventory_df["Status"] == status_filter]
else:
    filtered_inventory_df = inventory_df

st.subheader(f"Inventory - {status_filter}")
st.dataframe(filtered_inventory_df)

# Add bulk status update feature
#st.markdown("### Bulk Status Update")
#
## Add a checkbox for selecting all items
#select_all = st.checkbox("Select All")
#
## Add checkboxes for each row
#selected_items = []
#for index, row in filtered_inventory_df.iterrows():
#    col1, col2, col3, col4 = st.columns([0.05, 0.3, 0.3, 0.35])
#    with col1:
#        if select_all or st.checkbox("", key=f"select_{index}"):
#            selected_items.append(row)
#    with col2:
#        st.write(row["Name"])
#    with col3:
#        st.write(row["Catalog Number"])
#    with col4:
#        st.write(row["Status"])
#
#if selected_items:
#    new_status = st.selectbox("Change status to:", ["Requested", "Ordered", "Received"])
#    if st.button("Update Selected Items"):
#        for item in selected_items:
#            update_inventory_item(
#                item["Catalog Number"],
#                item["Vendor"],
#                item["Name"],
#                new_status,
#                item["Quantity"],
#                item["Requested By"],
#                item["Notes"]
#            )
#       st.success("Selected items updated successfully!")
#       st.rerun()





# Search functionality
search_query = st.text_input("Search inventory (by name, catalog number, or vendor):")
if search_query:
    filtered_df = inventory_df[inventory_df.apply(lambda row: search_query.lower() in row.to_string().lower(), axis=1)]

    if not filtered_df.empty:
        st.subheader("Search Results")
        st.dataframe(filtered_df)

        for index, row in filtered_df.iterrows():
            unique_key = f"action_{row['Catalog Number']}_{index}"

            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if st.button(f"Reorder {row['Name']}", key=f"reorder_{unique_key}"):
                    existing_item = get_item_by_catalog_and_vendor(row["Catalog Number"], row["Vendor"])
            
                    if existing_item:
                        # Update the item directly in the database
                        update_inventory_item(
                            row["Catalog Number"],
                            row["Vendor"],
                            row["Name"],
                            "Requested",
                            st.session_state['quantity'],  # Use the value from session state
                            row["Requested By"],
                            row["Notes"]
                        )
            
                        # Populate session state to update the sidebar with current values
                        st.session_state['catalog_number'] = row["Catalog Number"]
                        st.session_state['vendor'] = row["Vendor"]
                        st.session_state['name'] = row["Name"]
                        st.session_state['url'] = row["URL"]
                        st.session_state['quantity'] = int(row["Quantity"]) if pd.notnull(row["Quantity"]) else 1
                        st.session_state['unit'] = row["Unit"]
                        st.session_state['notes'] = row["Notes"]
                        st.session_state['cost'] = float(row["Cost"]) if pd.notnull(row["Cost"]) else 0.0
                        st.session_state['status'] = 'Requested'
                        st.session_state['requested_by'] = row["Requested By"]
            
                        st.success(f"Reordered item: {row['Name']} (Catalog: {row['Catalog Number']})")
                    else:
                        st.warning(f"Item not found in inventory: {row['Name']} (Catalog: {row['Catalog Number']})")
            
                    st.rerun()

            with col2:
                if st.button(f"Edit {row['Name']}", key=f"edit_{unique_key}"):
                    st.session_state['edit_mode'] = True
                    st.session_state['edit_catalog_number'] = row["Catalog Number"]
                    st.session_state['edit_vendor'] = row["Vendor"]
                    st.session_state['catalog_number'] = row["Catalog Number"]
                    st.session_state['vendor'] = row["Vendor"]
                    st.session_state['name'] = row["Name"]
                    st.session_state['quantity'] = int(row["Quantity"])
                    st.session_state['cost'] = float(row["Cost"]) if pd.notnull(row["Cost"]) else 0.0
                    st.session_state['status'] = row["Status"]
                    st.session_state['requested_by'] = row["Requested By"]
                    st.session_state['unit'] = row["Unit"] if pd.notnull(row["Unit"]) else ""
                    st.session_state['notes'] = row["Notes"] if pd.notnull(row["Notes"]) else ""
                    st.session_state['url'] = row["URL"] if pd.notnull(row["URL"]) else ""

                    st.success(f"Editing item: {row['Name']} (Catalog: {row['Catalog Number']})")
                    st.rerun()

                if st.button(f"Mark Ordered {row['Name']}", key=f"mark_ordered_{unique_key}"):
                    update_inventory_item(
                        row["Catalog Number"],
                        row["Vendor"],
                        row["Name"],
                        "Ordered",  # Change status to Ordered
                        row["Quantity"],
                        row["Requested By"],
                        row["Notes"]
                    )
                    st.success(f"Item '{row['Name']}' marked as Ordered.")
                    st.rerun()

            with col3:
                if st.button(f"Delete {row['Name']}", key=f"delete_{unique_key}"):
                    delete_inventory_item(row["Catalog Number"], row["Vendor"])
                    st.success(f"Deleted item: {row['Name']} (Catalog: {row['Catalog Number']})")
                    st.rerun()

                if st.button(f"Mark Received {row['Name']}", key=f"mark_received_{unique_key}"):
                    update_inventory_item(
                        row["Catalog Number"],
                        row["Vendor"],
                        row["Name"],
                        "Received",  # Change status to Received
                        row["Quantity"],
                        row["Requested By"],
                        row["Notes"]
                    )
                    st.success(f"Item '{row['Name']}' marked as Received.")
                    st.rerun()

            st.markdown("---")
    else:
        st.warning("No matching items found.")





# Import CSV
uploaded_file = st.file_uploader("Upload CSV File", type=['csv'])
if uploaded_file is not None:
    import_csv_to_db(uploaded_file)

st.divider()
st.header("Export/Import")

st.download_button(
    label="Download Template",
    data=download_csv_template().getvalue(),
    file_name="inventory_template.csv",
    mime="text/csv"
)

st.download_button("Download Inventory", inventory_df.to_csv(index=False), file_name="inventory.csv", mime="text/csv")

st.divider()
st.header("Manage Duplicates")

if st.button("Purge and Merge Duplicates"):
    purge_and_merge_duplicates()


# Sidebar form for adding new inventory item or editing existing items
# Sidebar form for adding new inventory item or editing existing items
if st.session_state.get('edit_mode', False):
    with st.sidebar:
        st.header("Edit Inventory Item")
        with st.form("edit_inventory"):
            requested_by = st.selectbox(
                "Requested By",
                ["Assaf Alon", "Zifang Deng", "Liatris Reevey", "Yixi Yang", "Anthony Vazquez"],
                index=["Assaf Alon", "Zifang Deng", "Liatris Reevey", "Yixi Yang", "Anthony Vazquez"].index(
                    st.session_state.get("requested_by", "Assaf Alon")
                )
            )
            catalog_number = st.text_input("Catalog Number", value=st.session_state['catalog_number'])
            vendor = st.text_input("Vendor", value=st.session_state['vendor'])
            name = st.text_input("Item Name", value=st.session_state['name'])
            url = st.text_input("Item URL", value=st.session_state['url'])
            quantity = st.number_input("Quantity", min_value=1, step=1, value=st.session_state['quantity'])
            unit = st.text_input("Unit", value=st.session_state['unit'])
            notes = st.text_area("Notes", value=st.session_state['notes'])
            cost = st.number_input("Cost ($)", min_value=0.0, step=0.01, value=st.session_state['cost'])
            status = st.selectbox("Status", ["Requested", "Ordered", "Received"], 
                                  index=["Requested", "Ordered", "Received"].index(st.session_state['status']))

            submit_button = st.form_submit_button("Save Changes")

            if submit_button:
                update_inventory_item(
                    st.session_state["edit_catalog_number"],
                    st.session_state["edit_vendor"],
                    name,  # Include the edited name field
                    status,
                    quantity,
                    requested_by,
                    notes
                )
                st.success(f"Item '{name}' updated successfully!")
                st.session_state['edit_mode'] = False  # Exit edit mode after save
                st.rerun()

else:
    with st.sidebar:
        st.header("Add New Inventory Item")
        with st.form("add_inventory"):
            requested_by = st.selectbox(
                "Requested By",
                ["Assaf Alon", "Zifang Deng", "Liatris Reevey", "Yixi Yang", "Anthony Vazquez"],
                index=["Assaf Alon", "Zifang Deng", "Liatris Reevey", "Yixi Yang", "Anthony Vazquez"].index(
                    st.session_state.get("requested_by", "Assaf Alon")
                )
            )
            catalog_number = st.text_input("Catalog Number", value=st.session_state.get('catalog_number', ''))
            vendor = st.text_input("Vendor", value=st.session_state.get('vendor', ''))
            name = st.text_input("Item Name", value=st.session_state.get('name', ''))
            url = st.text_input("Item URL", value=st.session_state.get('url', ''))
            quantity = st.number_input("Quantity", min_value=1, step=1, value=st.session_state.get('quantity', 1))
            unit = st.text_input("Unit", value=st.session_state.get('unit', ''))
            notes = st.text_area("Notes", value=st.session_state.get('notes', ''))
            cost = st.number_input("Cost ($)", min_value=0.0, step=0.01, value=st.session_state.get('cost', 0.0))
            status = st.selectbox("Status", ["Requested", "Ordered", "Received"], 
                                  index=["Requested", "Ordered", "Received"].index(st.session_state.get('status', 'Requested')))

            submit_button = st.form_submit_button("Add Item")

            if submit_button:
                # Check if item already exists
                existing_item = get_item_by_catalog_and_vendor(catalog_number, vendor)
                
                if existing_item:
                    # Update existing item
                    update_inventory_item(
                        catalog_number,
                        vendor,
                        name,
                        status,
                        quantity,
                        requested_by,
                        notes
                    )
                    st.success(f"Updated existing item: {name} (Catalog: {catalog_number})")
                else:
                    # Add new item if not found
                    add_inventory_item(requested_by, catalog_number, vendor, name, url, quantity, unit, notes, cost, status)
                    st.success(f"Item '{name}' added successfully!")

                st.rerun()
