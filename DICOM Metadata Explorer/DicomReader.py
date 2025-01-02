import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import pydicom
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from datetime import datetime
from PyQt5.QtWidgets import QFileDialog, QApplication
from matplotlib.widgets import Slider, Button

# Create QApplication instance
app = QApplication([])

def anonymize_dicom(dicom_data, prefix):
    """Anonymize DICOM file by replacing UIDs and sensitive fields with the provided prefix."""
    # Define sensitive tags, including SOPClassUID and SOPInstanceUID
    sensitive_tags = [
    # Patient Information
    (0x0010, 0x0010),  # Patient's Name
    (0x0010, 0x0020),  # Patient ID
    (0x0010, 0x0030),  # Patient Birth Date
    (0x0010, 0x0040),  # Patient Sex
    
    # Study Information
    (0x0020, 0x000D),  # Study Instance UID
    (0x0008, 0x0020),  # Study Date
    (0x0008, 0x0030),  # Study Time
    (0x0008, 0x0090),  # Referring Physician Name
    
    # Visit Information
    (0x0008, 0x0050),  # Accession Number
    (0x0010, 0x0024),  # Medical Record Number
    
    # Procedure and Image Information
    (0x0052, 0x0006),  # Procedure Code Sequence
    (0x0008, 0x0008),  # Image Type
    
    # Device and Equipment Information
    (0x0008, 0x0070),  # Manufacturer
    (0x0018, 0x1000),  # Device Serial Number
    
    # Radiology-specific Data
    (0x0054, 0x0220),  # View Position
    (0x0054, 0x0222),  # View Position Modifier
    
    # Other Sensitive Information
    (0x0008, 0x1030),  # Study Description
    (0x0020, 0x4000),  # Image Comments
]

    # Replace sensitive fields with the prefix
    for tag in sensitive_tags:
        if tag in dicom_data:
            dicom_data[tag].value = prefix  # Replace sensitive information with the prefix

    return dicom_data

def import_dicom():
    global dicom_data

    # Clear metadata text and combobox before loading new data
    metadata_text.delete("1.0", tk.END)
    metadata_combobox.set('')
    metadata_combobox['values'] = []

    ds, filepath_or_message = load_dicom_file()
    if ds:
        dicom_data = ds  # Store the loaded DICOM data
        messagebox.showinfo("Import Successful", f"Loaded DICOM file: {filepath_or_message}")
        
        # Update metadata combobox with available DICOM elements sorted alphabetically
        metadata_options = sorted([
            element.name
            for element in dicom_data
            if element.tag != (0x7FE0, 0x0010)
        ])
        metadata_combobox['values'] = metadata_options
        
        # Display the DICOM image after successful import
        if hasattr(ds, 'NumberOfFrames'):
            display_m2d(ds)  # For multi-frame DICOM
        else:
            display_dicom(ds)  # For single-frame DICOM
    else:
        messagebox.showerror("Import Failed", filepath_or_message)

def format_dicom_date(date_str):
    """Format DICOM date strings to YYYY-MM-DD format"""
    if not date_str or not isinstance(date_str, str):
        return date_str
    try:
        # Remove any dots or separators
        date_str = date_str.replace('.', '').replace('-', '')
        # Handle YYYYMMDD format
        if len(date_str) == 8:
            return datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
        return date_str
    except ValueError:
        return date_str

def format_dicom_time(time_str):
    """Format DICOM time strings to HH:MM:SS format"""
    if not time_str or not isinstance(time_str, str):
        return time_str
    try:
        # Remove any trailing fractional seconds and separators
        time_str = time_str.split('.')[0].replace(':', '')
        # Handle HHMMSS format
        if len(time_str) == 6:
            return datetime.strptime(time_str, "%H%M%S").strftime("%H:%M:%S")
        return time_str
    except ValueError:
        return time_str

def load_dicom_file():
    """Opens a file dialog to load a DICOM file."""
    try:
        options = QFileDialog.Options()
        filepath, _ = QFileDialog.getOpenFileName(
            None, "Open DICOM File", "", 
            "DICOM Files (*.dcm);;All Files (*)", 
            options=options)
        
        if not filepath:
            return None, "No file selected."
        ds = pydicom.dcmread(filepath)
        return ds, filepath
    except Exception as e:
        return None, f"Error loading file: {str(e)}"

def display_dicom(ds):
    """Displays a single DICOM image."""
    if ds is None:
        print("No file loaded.")
        return
    
    # Create a new figure and canvas
    fig, ax = plt.subplots()
    ax.imshow(ds.pixel_array, cmap='gray')
    ax.set_title("DICOM Viewer")
    ax.axis('off')
    
    # Create a canvas widget and pack it into the image_frame
    canvas = FigureCanvasTkAgg(fig, master=image_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

def display_m2d(ds):
    """Displays M2D (multi-frame) DICOM files with a slider."""
    try:
        frames = ds.pixel_array
        print(f"Frame shape: {frames.shape}")
        
        # Clear previous widgets in image_frame
        for widget in image_frame.winfo_children():
            widget.destroy()
            
        fig, ax = plt.subplots(figsize=(10, 8))
        plt.subplots_adjust(bottom=0.2)
        
        im = ax.imshow(frames[0])
        ax.set_title(f"Frame 1/{len(frames)}")
        ax.axis('off')
        
        slider_ax = plt.axes([0.1, 0.05, 0.8, 0.03])
        slider = Slider(slider_ax, 'Frame', 0, len(frames)-1, valinit=0, valstep=1)
        
        def update(val):
            try:
                frame_idx = int(slider.val)
                if 0 <= frame_idx < len(frames):
                    im.set_array(frames[frame_idx])
                    ax.set_title(f"Frame {frame_idx+1}/{len(frames)}")
                    fig.canvas.draw_idle()
            except Exception as e:
                print(f"Error updating frame: {e}")
        
        slider.on_changed(update)
        
        # Add play/pause functionality
        play_ax = plt.axes([0.1, 0.1, 0.1, 0.04])
        play_button = Button(play_ax, 'Play')
        
        is_playing = [False]
        anim = None
        
        def animate(frame):
            if is_playing[0]:
                try:
                    current_frame = int(slider.val)
                    next_frame = (current_frame + 1) % len(frames)
                    slider.set_val(next_frame)
                except Exception as e:
                    print(f"Animation error: {e}")
                    is_playing[0] = False
                    play_button.label.set_text('Play')
            return [im]
            
        def play(event):
            nonlocal anim
            is_playing[0] = not is_playing[0]
            play_button.label.set_text('Pause' if is_playing[0] else 'Play')
            
            if is_playing[0]:
                anim = animation.FuncAnimation(fig, animate, interval=300, blit=True)
            else:
                if anim is not None:
                    anim.event_source.stop()
        
        play_button.on_clicked(play)
        
        # Create a canvas widget and pack it into the image_frame
        canvas = FigureCanvasTkAgg(fig, master=image_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
    except Exception as e:
        messagebox.showerror("Error", f"Error displaying image: {e}")

def anonymize_file():
    """Anonymize selected DICOM file."""
    global dicom_data

    if dicom_data is None:
        messagebox.showwarning("No DICOM File", "Please load a DICOM file first.")
        return

    prefix = prefix_entry.get()
    if not prefix:
        messagebox.showwarning("No Prefix", "Please provide a prefix for anonymization.")
        return

    try:
        # Anonymize the DICOM file using the prefix
        dicom_data = anonymize_dicom(dicom_data, prefix)

        # Save the anonymized file
        save_path = filedialog.asksaveasfilename(defaultextension=".dcm",
                                                filetypes=[("DICOM files", "*.dcm")])
        if save_path:
            dicom_data.save_as(save_path)  # Use save_as to save the DICOM file
            messagebox.showinfo("Anonymization", f"DICOM file has been anonymized and saved as {save_path}")
        else:
            messagebox.showinfo("Save Canceled", "File was not saved.")
    except Exception as e:
        messagebox.showerror("Error", f"Anonymization failed: {e}")
        
def explore_group(group_name):
    """Explore the values of a specific DICOM group."""
    global dicom_data

    if dicom_data is not None:
        metadata_text.delete("1.0", tk.END)
        
        # Define DICOM groups and their corresponding tags
        group_tags = {
    "Study Information": [
        (0x0020, 0x000D),  # Study Instance UID
        (0x0008, 0x0020),  # Study Date
        (0x0008, 0x0030),  # Study Time
        (0x0008, 0x0090),  # Referring Physician Name
    ],
    "Series Information": [
        (0x0020, 0x000E),  # Series Instance UID
        (0x0008, 0x0060),  # Modality
        (0x0008, 0x103E),  # Series Description
    ],
    "Patient Information": [
        (0x0010, 0x0010),  # Patient's Name
        (0x0010, 0x0020),  # Patient ID
        (0x0010, 0x0030),  # Patient Birth Date
        (0x0010, 0x0040),  # Patient Sex
    ],
    "Image Acquisition Parameters": [
        (0x0018, 0x5100),  # Private Creator
        (0x0018, 0x1152),  # Exposure Time
        (0x0018, 0x1150),  # Exposure
    ],
    "Equipment Information": [
        (0x0008, 0x0070),  # Manufacturer
        (0x0018, 0x1000),  # Device Serial Number
    ],
    "Image-Specific Data": [
        (0x0020, 0x0032),  # Image Position (Patient)
        (0x0020, 0x0037),  # Image Orientation (Patient)
    ],
    "Image Information": [
        (0x0008, 0x0060),  # Modality
        (0x0020, 0x0032),  # Image Position (Patient)
        (0x0020, 0x0037),  # Image Orientation (Patient)
        (0x0028, 0x0030),  # Pixel Spacing
        (0x0028, 0x0100),  # Bits Allocated
        (0x0028, 0x0101),  # Bits Stored
        (0x0028, 0x0102),  # High Bit
        (0x0028, 0x1050),  # Window Center
        (0x0028, 0x1051),  # Window Width
        (0x0028, 0x1052),  # Rescale Intercept
        (0x0028, 0x1053),  # Rescale Slope
        (0x0018, 0x0050),  # Slice Thickness
    ],
    "Sensitive Data": [
        # Patient Information
    (0x0010, 0x0010),  # Patient's Name
    (0x0010, 0x0020),  # Patient ID
    (0x0010, 0x0030),  # Patient Birth Date
    (0x0010, 0x0040),  # Patient Sex
    
    # Study Information
    (0x0020, 0x000D),  # Study Instance UID
    (0x0008, 0x0020),  # Study Date
    (0x0008, 0x0030),  # Study Time
    (0x0008, 0x0090),  # Referring Physician Name
    
    # Visit Information
    (0x0008, 0x0050),  # Accession Number
    (0x0010, 0x0024),  # Medical Record Number
    
    # Procedure and Image Information
    (0x0052, 0x0006),  # Procedure Code Sequence
    (0x0008, 0x0008),  # Image Type
    
    # Device and Equipment Information
    (0x0008, 0x0070),  # Manufacturer
    (0x0018, 0x1000),  # Device Serial Number
    
    # Radiology-specific Data
    (0x0054, 0x0220),  # View Position
    (0x0054, 0x0222),  # View Position Modifier
    
    # Other Sensitive Information
    (0x0008, 0x1030),  # Study Description
    (0x0020, 0x4000),  # Image Comments
    ],
    "All" : []
        }

        # Get the tags for the selected group
        selected_group_tags = group_tags.get(group_name)
        if selected_group_tags is not None:
            if group_name == "All":
                selected_group_tags = [
                    element.tag
                    for element in dicom_data
                    if element.tag != (0x7FE0, 0x0010)
                ]
            for tag in selected_group_tags:
                element = dicom_data.get(tag)
                if element:
                    value = element.value
                    if "Date" in element.name:
                        formatted_value = format_dicom_date(str(value))
                        metadata_text.insert(tk.END, f"({hex(element.tag.group)}, {hex(element.tag.element)}) {element.name}: {formatted_value}\n")
                    elif "Time" in element.name:
                        formatted_value = format_dicom_time(str(value))
                        metadata_text.insert(tk.END, f"({hex(element.tag.group)}, {hex(element.tag.element)}) {element.name}: {formatted_value}\n")
                    else:
                        metadata_text.insert(tk.END, f"({hex(element.tag.group)}, {hex(element.tag.element)}) {element.name}: {value}\n")
        else:
            metadata_text.insert(tk.END, "No metadata available for this group.")

def display_metadata(event):
    """Display selected metadata for the DICOM file."""
    global dicom_data
    selected_metadata = metadata_combobox.get()

    if dicom_data is not None:
        metadata_text.delete("1.0", tk.END)

        # Find and display the corresponding metadata field
        for element in dicom_data:
            if element.name == selected_metadata:
                value = element.value
                # Format the date or time if needed
                if "Date" in element.name:
                    formatted_value = format_dicom_date(str(value))
                    metadata_text.insert(tk.END, f"({hex(element.tag.group)}, {hex(element.tag.element)}) {element.name}: {formatted_value}\n")
                elif "Time" in element.name:
                    formatted_value = format_dicom_time(str(value))
                    metadata_text.insert(tk.END, f"({hex(element.tag.group)}, {hex(element.tag.element)}) {element.name}: {formatted_value}\n")
                else:
                    metadata_text.insert(tk.END, f"({hex(element.tag.group)}, {hex(element.tag.element)}) {element.name}: {value}\n")

def search_metadata():
    """Search through DICOM metadata for a specific term."""
    global dicom_data
    
    search_term = search_entry.get().lower()
    
    if dicom_data is None:
        messagebox.showwarning("No DICOM File", "Please load a DICOM file first.")
        return

    metadata_text.delete("1.0", tk.END)
    found_matches = False

    for element in dicom_data:
        # Convert to string and make case-insensitive
        element_name = str(element.name).lower()
        element_value = str(element.value).lower()

        # Check if search term is in name or value
        if search_term in element_name or search_term in element_value:
            value = element.value
            if "Date" in element.name:
                formatted_value = format_dicom_date(str(value))
                metadata_text.insert(tk.END, f"({hex(element.tag.group)}, {hex(element.tag.element)}) {element.name}: {formatted_value}\n")
            elif "Time" in element.name:
                formatted_value = format_dicom_time(str(value))
                metadata_text.insert(tk.END, f"({hex(element.tag.group)}, {hex(element.tag.element)}) {element.name}: {formatted_value}\n")
            else:
                metadata_text.insert(tk.END, f"({hex(element.tag.group)}, {hex(element.tag.element)}) {element.name}: {value}\n")
            found_matches = True

    if not found_matches:
        metadata_text.insert(tk.END, "No matches found.")

# Initialize global variables
dicom_data = None
image_type = None

# Create the main window
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Advanced DICOM Viewer")

    # Anonymization frame at the top
    anonymization_frame = tk.Frame(root)
    anonymization_frame.pack(fill=tk.X, padx=10, pady=5)

    prefix_label = tk.Label(anonymization_frame, text="Anonymization Prefix:")
    prefix_label.pack(side=tk.LEFT)

    prefix_entry = tk.Entry(anonymization_frame, width=20)
    prefix_entry.pack(side=tk.LEFT, padx=5)

    anonymize_button = tk.Button(anonymization_frame, text="Anonymize DICOM File", command=anonymize_file)
    anonymize_button.pack(side=tk.LEFT)

    import_button = tk.Button(anonymization_frame, text="Import DICOM File", command=import_dicom)
    import_button.pack(side=tk.LEFT, padx=5)

    # Create main container
    main_container = tk.Frame(root)
    main_container.pack(fill=tk.BOTH, expand=True)

    # Create buttons for each DICOM group
    def create_group_buttons():
        """Create buttons for each DICOM group."""
        groups = [
            "Study Information",
            "Series Information", 
            "Patient Information",
            "Image Acquisition Parameters",
            "Equipment Information",
            "Image-Specific Data",
            "Image Information",
            "Sensitive Data",
        ]

        button_frame = tk.Frame(main_container)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        for group in groups:
            group_button = tk.Button(button_frame, text=group, command=lambda g=group: explore_group(g))
            group_button.pack(side=tk.LEFT, padx=5)

        # Add button to display all data
        all_data_button = tk.Button(button_frame, text="All Data", command=lambda: explore_group("All"))
        all_data_button.pack(side=tk.LEFT, padx=5)

    # Create group buttons
    create_group_buttons()

    # Search frame
    search_frame = tk.Frame(main_container)
    search_frame.pack(fill=tk.X, padx=10, pady=5)

    search_label = tk.Label(search_frame, text="Search:")
    search_label.pack(side=tk.LEFT)

    search_entry = tk.Entry(search_frame, width=40)
    search_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

    search_button = tk.Button(search_frame, text="Search", command=search_metadata)
    search_button.pack(side=tk.LEFT)

    # Metadata and controls frame
    top_frame = tk.Frame(main_container)
    top_frame.pack(fill=tk.BOTH, expand=True)

    # Metadata combobox
    metadata_combobox = ttk.Combobox(top_frame, state='readonly')
    metadata_combobox.pack(fill=tk.X, padx=10, pady=5)
    metadata_combobox.bind("<<ComboboxSelected>>", display_metadata)

    # Metadata display text widget
    metadata_text = tk.Text(top_frame, height=10, wrap=tk.WORD)
    metadata_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    # Image display frame
    image_frame = tk.Frame(main_container)
    image_frame.pack(fill=tk.BOTH, expand=True)

    # Start the GUI event loop
    root.mainloop()
