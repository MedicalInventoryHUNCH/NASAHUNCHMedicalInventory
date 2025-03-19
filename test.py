import customtkinter
from pymongo import MongoClient
from PIL import Image
import threading
import datetime
import os
import json
import tkinter.messagebox as messagebox  # Import messagebox for confirmation dialogs
import socket
import time

# File configuration
DATA_FILE = "inventory.txt"
LOG_FILE = "database_logs.txt"

# Initially, we assume offline mode
OFFLINE_MODE = True


def check_internet_connection():
    """Check for an active internet connection."""
    try:
        # Try connecting to a well-known DNS server (Google's 8.8.8.8) on port 53
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False


class InventoryManager:
    @staticmethod
    def read_items():
        """Read items from text file and return as list of dictionaries"""
        items = []
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                for line in f:
                    item = json.loads(line.strip())  # Use JSON for safe serialization
                    items.append(item)
        return items

    @staticmethod
    def write_items(items):
        # Write list of items to text file
        with open(DATA_FILE, "w") as f:
            for item in items:
                f.write(json.dumps(item) + "\n")

    @staticmethod
    def get_next_id():
        # Get next available ID
        items = InventoryManager.read_items()
        if not items:
            return 1
        return max(item["_id"] for item in items) + 1


class MongoDBManager:
    # Initialize connection attributes to None
    cluster = None
    db = None
    collection = None
    offline_mode = True

    @staticmethod
    def init_connection():
        """Attempt to initialize a connection to MongoDB."""
        try:
            # Attempt connection with a short timeout
            MongoDBManager.cluster = MongoClient(
                "mongodb+srv://bernardorhyshunch:TakingInventoryIsFun@cluster0.jpb6w.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0",
                serverSelectionTimeoutMS=3000
            )
            # Test connection
            MongoDBManager.cluster.admin.command('ping')
            MongoDBManager.db = MongoDBManager.cluster["Inventory"]
            MongoDBManager.collection = MongoDBManager.db["Inventory"]
            MongoDBManager.offline_mode = False
            print("MongoDB connection established.")
        except Exception as e:
            MongoDBManager.offline_mode = True
            print("Failed to connect to MongoDB:", e)

    @staticmethod
    def sync_with_txt():
        """Synchronize MongoDB collection with the contents of the text file if online."""
        if MongoDBManager.offline_mode:
            return
        items = InventoryManager.read_items()
        try:
            MongoDBManager.collection.delete_many({})
            if items:
                MongoDBManager.collection.insert_many(items)
            print("MongoDB sync successful.")
        except Exception as e:
            print("MongoDB sync failed:", e)

    @staticmethod
    def check_and_sync():
        """Check for internet connectivity and update MongoDB if possible."""
        if check_internet_connection():
            if MongoDBManager.offline_mode:
                # Attempt to initialize connection
                MongoDBManager.init_connection()
                if not MongoDBManager.offline_mode:
                    # If connection established, sync data
                    MongoDBManager.sync_with_txt()
            else:
                # Already online, perform regular sync
                MongoDBManager.sync_with_txt()
        else:
            MongoDBManager.offline_mode = True


def background_sync():
    """Background thread function that periodically checks connectivity and syncs data."""
    while True:
        time.sleep(60)  # Check every 60 seconds
        MongoDBManager.check_and_sync()


class ToplevelWindow(customtkinter.CTkToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.geometry("1280x720")
        self.title("Details / Logs")
        self.resizable(True, True)

        # Modern styling
        customtkinter.set_appearance_mode("dark")
        self.configure(fg_color=("#DBDBDB", "#2B2B2B"))

        # Textbox styling
        self.LogsTextBox = customtkinter.CTkTextbox(
            self,
            font=("Segoe UI", 12),
            wrap="word",
            fg_color=("#FFFFFF", "#1E1E1E"),
            border_width=1,
            border_color=("#AAAAAA", "#444444"),
            state="disabled"
        )
        self.LogsTextBox.pack(padx=20, pady=20, fill="both", expand=True)

        # Scrollbar setup in __init__ to ensure only one exists
        self.scrollbar = customtkinter.CTkScrollbar(
            self,
            command=self.LogsTextBox.yview,
            button_color=("#3B8ED0", "#1F6AA5")
        )
        self.scrollbar.pack(side="right", fill="y")
        self.LogsTextBox.configure(yscrollcommand=self.scrollbar.set)

        self.display_logs()

    def display_logs(self):
        log_filename = "database_logs.txt"

        self.LogsTextBox.configure(state='normal')
        self.LogsTextBox.delete("1.0", "end")

        if os.path.exists(log_filename):
            with open(log_filename, "r") as log_file:
                logs = log_file.read()
                self.LogsTextBox.insert("0.0", logs)
        else:
            self.LogsTextBox.insert("0.0", "No logs available.\n")

        self.LogsTextBox.configure(state='disabled')

        self.grab_set()
        self.focus_force()
        self.after(200, self.release_grab)

    def release_grab(self):
        self.grab_release()


class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        self.geometry("1024x600")  # Default size if not maximized

        self.grid_columnconfigure(0, weight=1)  # Left column (input fields)
        self.grid_columnconfigure(1, weight=3)  # Right column (document display)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # Set appearance
        customtkinter.set_appearance_mode("dark")
        customtkinter.set_default_color_theme("dark-blue")
        self.title("Medical Inventory System")
        self.minsize(800, 600)

        self.toplevel_window = None

        self.bind("<F11>", lambda event: self.toggle_maximize())

        self.item_names = []
        self.refresh_dropdown()

        # Title Label
        self.TitleLabel = customtkinter.CTkLabel(
            self, text="Medical Inventory System", text_color="White", font=("Arial", 24, "bold")
        )
        self.TitleLabel.grid(row=0, column=0, columnspan=3, pady=20)

        # Add Item Section
        self.AddItemFrame = customtkinter.CTkFrame(self, corner_radius=10)
        self.AddItemFrame.grid(row=1, column=0, padx=20, pady=20, sticky="nsew")

        self.AddItemLabel = customtkinter.CTkLabel(self.AddItemFrame, text="Add New Item", font=("Arial", 18))
        self.AddItemLabel.grid(row=0, column=0, columnspan=2, pady=10)

        self.AddNameBox = customtkinter.CTkEntry(self.AddItemFrame, placeholder_text="Enter Item Name", width=300)
        self.AddNameBox.grid(row=1, column=0, columnspan=2, padx=10, pady=5)

        self.AddAmountBox = customtkinter.CTkEntry(
            self.AddItemFrame,
            placeholder_text="Enter Doses",
            width=300
        )
        self.AddAmountBox.grid(row=2, column=0, columnspan=2, padx=10, pady=5)

        # Expiration Date Entry Box with four-digit year
        self.AddExpiry = customtkinter.CTkEntry(self.AddItemFrame, placeholder_text="Enter Expiration Date: MM/DD/YYYY",
                                                width=300)
        self.AddExpiry.grid(row=3, column=0, columnspan=2, padx=10, pady=5)

        self.AddDescription = customtkinter.CTkEntry(self.AddItemFrame, placeholder_text="Enter Description", width=300)
        self.AddDescription.grid(row=4, column=0, columnspan=2, padx=10, pady=5)

        self.AddButton = customtkinter.CTkButton(
            self.AddItemFrame, text="Add Item", command=self.addstuff, width=150
        )
        self.AddButton.grid(row=5, column=0, columnspan=2, padx=10, pady=10)

        # Edit Section
        self.EditFrame = customtkinter.CTkFrame(self, corner_radius=10)
        self.EditFrame.grid(row=2, column=0, padx=20, pady=20, sticky="nsew")

        self.EditItemLabel = customtkinter.CTkLabel(self.EditFrame, text="Edit Existing Item", font=("Arial", 18))
        self.EditItemLabel.grid(row=0, column=0, columnspan=2, pady=10)

        self.CurrentDocumentsDropdown = customtkinter.CTkOptionMenu(
            self.EditFrame, values=self.item_names, width=200
        )
        self.CurrentDocumentsDropdown.grid(row=1, column=0, columnspan=2, padx=10, pady=5)

        # Change Name
        self.EditSelectedName = customtkinter.CTkEntry(self.EditFrame, placeholder_text="Enter New Name", width=300)
        self.EditSelectedName.grid(row=2, column=0, padx=10, pady=5)

        self.EditSelectedAmount = customtkinter.CTkEntry(
            self.EditFrame,
            placeholder_text="Enter New Doses",
            width=300
        )
        self.EditSelectedAmount.grid(row=3, column=0, padx=10, pady=5)

        self.EditSelectedExpiry = customtkinter.CTkEntry(self.EditFrame,
                                                         placeholder_text="Enter New Expiration Date: MM/DD/YYYY",
                                                         width=300)
        self.EditSelectedExpiry.grid(row=4, column=0, padx=10, pady=5)

        # New description field in edit section
        self.EditSelectedDescription = customtkinter.CTkEntry(self.EditFrame, placeholder_text="Enter New Description",
                                                              width=300)
        self.EditSelectedDescription.grid(row=5, column=0, padx=10, pady=5)

        self.UpdateButton = customtkinter.CTkButton(
            self.EditFrame, text="Update", command=self.update_name_amount, width=100
        )
        self.UpdateButton.grid(row=6, column=0, padx=10, pady=10)

        self.ViewLogsButton = customtkinter.CTkButton(
            self, text="Logs", command=self.view_logs, width=200
        )
        self.ViewLogsButton.grid(row=3, column=0, padx=20, pady=20)

        self.DeleteButton = customtkinter.CTkButton(
            self.EditFrame, text="Delete Item", command=self.delete_item, width=100,
            fg_color=("#E55353", "#CC4A4A"), hover_color=("#CC4A4A", "#B34141")
        )
        self.DeleteButton.grid(row=6, column=2, columnspan=2, padx=10, pady=10)

        # Documents Display Section (modified to include search)
        self.DocumentFrame = customtkinter.CTkFrame(self, corner_radius=10)
        self.DocumentFrame.grid(row=1, column=1, rowspan=3, padx=20, pady=20, sticky="nsew")
        self.DocumentFrame.grid_columnconfigure(0, weight=1)
        self.DocumentFrame.grid_rowconfigure(2, weight=1)

        # Search Frame
        self.SearchFrame = customtkinter.CTkFrame(self.DocumentFrame, fg_color="transparent")
        self.SearchFrame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

        self.SearchEntry = customtkinter.CTkEntry(
            self.SearchFrame,
            placeholder_text="Search items...",
            width=200
        )
        self.SearchEntry.grid(row=0, column=0, padx=(0, 10), pady=5)
        self.SearchEntry.bind("<Return>", lambda event: self.perform_search())

        self.SearchButton = customtkinter.CTkButton(
            self.SearchFrame,
            text="Search",
            command=self.perform_search,
            width=80
        )
        self.SearchButton.grid(row=0, column=1, padx=0, pady=5)

        # Document Label
        self.DocumentLabel = customtkinter.CTkLabel(self.DocumentFrame, text="Current Inventory", font=("Arial", 18))
        self.DocumentLabel.grid(row=1, column=0, pady=10, sticky="n")

        # Document Textbox
        self.DocumentTextbox = customtkinter.CTkTextbox(
            self.DocumentFrame,
            wrap="none",
            state="disabled",
            font=("Consolas", 12)
        )
        self.DocumentTextbox.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")
        self.DocumentTextbox.tag_config("highlight", background="#FE9000")

        # Initial display of documents
        self.refresh_document_display()

        self.item_names = []
        self.CurrentDocumentsDropdown = customtkinter.CTkOptionMenu(
            self.EditFrame, values=self.item_names, width=200
        )
        self.CurrentDocumentsDropdown.grid(row=1, column=0, columnspan=2, padx=10, pady=5)

        self.refresh_dropdown()

    def refresh_dropdown(self):
        # Refresh dropdown with current item names
        items = InventoryManager.read_items()
        self.item_names = [item["Item"] for item in items]
        if hasattr(self, 'CurrentDocumentsDropdown'):
            self.CurrentDocumentsDropdown.configure(values=self.item_names)

    def write_to_log(self, action, details):
        # Write to log file
        with open(LOG_FILE, "a") as log_file:
            timestamp = datetime.datetime.now().strftime("%m/%d/%Y %H:%M")
            log_file.write(f"[{timestamp}] {action}: {details}\n")

    def addstuff(self):
        name = self.AddNameBox.get().strip()
        amount = self.AddAmountBox.get().strip()
        expiry_str = self.AddExpiry.get().strip()
        description = self.AddDescription.get().strip()

        if name and amount:
            try:
                items = InventoryManager.read_items()
                new_item = {
                    "_id": InventoryManager.get_next_id(),
                    "Item": name,
                    "Doses": int(amount)
                }
                if expiry_str:
                    expiry_date = datetime.datetime.strptime(expiry_str, "%m/%d/%Y")
                    new_item["Expiry"] = expiry_date.strftime("%m/%d/%Y")
                if description:
                    new_item["Description"] = description
                items.append(new_item)
                InventoryManager.write_items(items)
                self.write_to_log("Add", f"Added item '{name}' with ID {new_item['_id']}")
                print(f"Item added successfully with ID {new_item['_id']}!")
                self.refresh_dropdown()
                self.refresh_document_display()
                # Attempt to sync with MongoDB (will sync only if online)
                MongoDBManager.sync_with_txt()
            except Exception as e:
                print(f"Error adding item: {e}")
        else:
            print("Please fill in both name and amount fields.")

    def update_name_amount(self):
        original_name = self.CurrentDocumentsDropdown.get()
        selected_item_name = self.CurrentDocumentsDropdown.get()
        new_name = self.EditSelectedName.get().strip()
        new_amount = self.EditSelectedAmount.get().strip()
        new_expiry = self.EditSelectedExpiry.get().strip()
        new_description = self.EditSelectedDescription.get().strip()

        items = InventoryManager.read_items()
        item_to_update = next((item for item in items if item["Item"] == selected_item_name), None)

        if not item_to_update:
            print("Item not found!")
            return

        if new_name:
            item_to_update["Item"] = new_name
        if new_amount:
            item_to_update["Doses"] = int(new_amount)
        if new_expiry:
            try:
                expiry_date = datetime.datetime.strptime(new_expiry, "%m/%d/%Y")
                item_to_update["Expiry"] = expiry_date.strftime("%m/%d/%Y")
            except ValueError:
                print("Invalid expiry date format")
                return
        if new_description:
            item_to_update["Description"] = new_description

        InventoryManager.write_items(items)
        self.write_to_log("Update", f"Updated item '{original_name}'")
        self.refresh_dropdown()
        self.refresh_document_display()
        # Attempt to sync with MongoDB (will sync only if online)
        MongoDBManager.sync_with_txt()

    def view_logs(self):
        if self.toplevel_window is None or not self.toplevel_window.winfo_exists():
            self.toplevel_window = ToplevelWindow(self)
        else:
            self.toplevel_window.focus_force()

    def delete_item(self):
        selected_item_name = self.CurrentDocumentsDropdown.get()
        # Ask for confirmation before deleting
        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{selected_item_name}'?"):
            return

        items = InventoryManager.read_items()
        new_items = [item for item in items if item["Item"] != selected_item_name]
        if len(new_items) == len(items):
            print("Item not found!")
            return
        InventoryManager.write_items(new_items)
        self.write_to_log("Delete", f"Deleted item '{selected_item_name}'")
        self.refresh_dropdown()
        self.refresh_document_display()
        # Attempt to sync deletion to MongoDB (will sync only if online)
        MongoDBManager.sync_with_txt()

    def perform_search(self):
        """Highlight documents containing the search query"""
        query = self.SearchEntry.get().strip().lower()
        self.DocumentTextbox.configure(state="normal")
        self.DocumentTextbox.tag_remove("highlight", "1.0", "end")
        if query:
            start_idx = "1.0"
            while True:
                sep_start = self.DocumentTextbox.search("-" * 40, start_idx, stopindex="end")
                if not sep_start:
                    block_text = self.DocumentTextbox.get(start_idx, "end-1c")
                    if any(query in line.lower() for line in block_text.split("\n")):
                        self.DocumentTextbox.tag_add("highlight", start_idx, "end-1c")
                    break
                sep_end = self.DocumentTextbox.index(f"{sep_start} lineend")
                block_text = self.DocumentTextbox.get(start_idx, sep_end)
                if any(query in line.lower() for line in block_text.split("\n")):
                    self.DocumentTextbox.tag_add("highlight", start_idx, sep_end)
                start_idx = self.DocumentTextbox.index(f"{sep_end} + 1 char")
        self.DocumentTextbox.configure(state="disabled")

    def refresh_document_display(self):
        """Fetches and displays all documents from text file"""
        try:
            self.DocumentTextbox.configure(state="normal")
            self.DocumentTextbox.delete("1.0", "end")
            items = InventoryManager.read_items()
            for item in items:
                doc_str = f"ID: {item['_id']}\n"
                doc_str += f"Item: {item['Item']}\n"
                doc_str += f"Doses: {item['Doses']}\n"
                if "Expiry" in item:
                    doc_str += f"Expiry: {item['Expiry']}\n"
                if "Description" in item:
                    doc_str += f"Description: {item['Description']}\n"
                doc_str += "-" * 40 + "\n"
                self.DocumentTextbox.insert("end", doc_str)
            self.DocumentTextbox.configure(state="disabled")
        except Exception as e:
            print(f"Error refreshing document display: {e}")
            self.DocumentTextbox.configure(state="disabled")
        finally:
            self.DocumentTextbox.configure(state="disabled")

    def toggle_maximize(self):
        # Toggle between maximized and windowed mode if desired
        if self.state() == "normal":
            self.state("zoomed")
        else:
            self.state("normal")


# Start the background sync thread (daemon thread so it exits with the app)
threading.Thread(target=background_sync, daemon=True).start()

app = App()
app.mainloop()
