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
    sensitive_tags = {
    #"Clean Pixel Data"
        # Tags that may contain pixel data with identification information
        (0x0008, 0x0008),  # Image Type
        (0x0052, 0x0006),  # Procedure Code Sequence
    #"Clean Recognizable Visual Features"
        # Tags that may lead to visual identification of individuals
        (0x0010, 0x0010),  # Patient's Name
        (0x0010, 0x0020),  # Patient ID
        (0x0010, 0x0030),  # Patient Birth Date
        (0x0010, 0x0040),  # Patient Sex
        (0x0008, 0x0020),  # Study Date
        (0x0008, 0x0030),  # Study Time
        (0x0008, 0x0090),  # Referring Physician Name
        (0x0008, 0x0050),  # Accession Number
        (0x0010, 0x0024),  # Medical Record Number
    #"Clean Graphics"
        # Tags that may contain identification information encoded as graphics or text annotations
        (0x0008, 0x0070),  # Manufacturer
        (0x0018, 0x1000),  # Device Serial Number
    #"Clean Structured Content"
        # Tags that may contain structured report information
        (0x0054, 0x0220),  # View Position
        (0x0054, 0x0222),  # View Position Modifier
    #"Clean Descriptors"
        # Tags that contain descriptive information which may include sensitive data
        (0x0008, 0x1030),  # Study Description
        (0x0020, 0x4000),  # Image Comments
}

    # Replace sensitive fields with the prefix
    for tag in sensitive_tags:
        if tag in dicom_data:
            dicom_data[tag].value = prefix  # Replace sensitive information with the prefix

    return dicom_data

def import_dicom():
    global dicom_data

    # Clear any existing data and UI elements related to the previous file
    dicom_data = None
    metadata_text.delete("1.0", tk.END)
    metadata_combobox.set('')
    metadata_combobox['values'] = []
    
    # Clear any previous image display
    for widget in image_frame.winfo_children():
        widget.destroy()

    # Load the new DICOM file
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
        if hasattr(ds, 'NumberOfFrames') and len(ds.pixel_array.shape) == 3:
            display_3d_grid(ds)  # For 3D DICOM volume
        elif hasattr(ds, 'NumberOfFrames'):
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
            
        fig, ax = plt.subplots(figsize=(15, 12))
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

def display_3d_grid(ds):
    """Displays a 3D DICOM volume as a grid of slices."""
    try:
        slices = ds.pixel_array  # Load 3D volume slices
        print(f"Volume shape: {slices.shape}")  # (depth, height, width)

        # Clear previous widgets in image_frame
        for widget in image_frame.winfo_children():
            widget.destroy()

        # Grid configuration
        num_slices = slices.shape[0]  # Number of 2D slices
        grid_cols = int(np.ceil(np.sqrt(num_slices)))  # Number of columns
        grid_rows = int(np.ceil(num_slices / grid_cols))  # Number of rows

        fig, axes = plt.subplots(grid_rows, grid_cols, figsize=(90, 75))  # Increase figure size
        axes = axes.flatten()

        # Plot each slice
        for idx, ax in enumerate(axes):
            if idx < num_slices:
                ax.imshow(slices[idx], cmap='gray')
                ax.axis('off')
            else:
                ax.axis('off')  # Hide unused axes

        # Adjust layout
        plt.tight_layout()
        ax.set_title(f"Slices {num_slices}")

        # Add button for showing individual slices
        show_slices_button = tk.Button(image_frame, text="Show Individual Slices", 
                                       command=lambda: show_slices(ds))
        show_slices_button.pack(pady=10)

        # Create a canvas widget and pack it into the image_frame
        canvas = FigureCanvasTkAgg(fig, master=image_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    except Exception as e:
        messagebox.showerror("Error", f"Error displaying 3D grid: {e}")

def show_slices(ds):
    """Opens a new window to display DICOM slices with navigation controls."""
    # Create a new top-level window
    slice_window = tk.Toplevel()
    slice_window.title("DICOM Slice Viewer")
    slice_window.geometry("800x900")  # Adjust size as needed

    class SliceViewer:
        def __init__(self, master, slices):
            self.master = master
            self.slices = slices
            self.current_slice = 0
            self.total_slices = len(slices)

            # Create main container
            self.main_container = tk.Frame(master)
            self.main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            # Create counter frame at the top
            self.counter_frame = tk.Frame(master)
            self.counter_frame.pack(fill=tk.X, padx=10, pady=5)

            # Create slice counter with larger font and prominent display
            self.counter_label = tk.Label(
                self.counter_frame, 
                text=f"Slice {self.current_slice + 1} of {self.total_slices}",
                font=("Arial", 16, "bold"),
                bg='lightgray',
                pady=5
            )
            self.counter_label.pack(fill=tk.X)

            # Create figure and canvas for the image
            self.fig, self.ax = plt.subplots(figsize=(8, 8))
            self.canvas = FigureCanvasTkAgg(self.fig, master=self.main_container)
            self.canvas.draw()
            self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            # Create navigation frame
            self.nav_frame = tk.Frame(master)
            self.nav_frame.pack(fill=tk.X, padx=10, pady=10)

            # Create navigation buttons with improved styling
            button_style = {
                'width': 20,
                'height': 2,
                'font': ('Arial', 12),
                'bg': '#4a90e2',
                'fg': 'white',
                'relief': tk.RAISED
            }

            self.prev_button = tk.Button(
                self.nav_frame,
                text="← Previous",
                command=self.show_previous_slice,
                **button_style
            )
            self.prev_button.pack(side=tk.LEFT, padx=20)

            self.next_button = tk.Button(
                self.nav_frame,
                text="Next →",
                command=self.show_next_slice,
                **button_style
            )
            self.next_button.pack(side=tk.RIGHT, padx=20)

            # Add keyboard bindings
            master.bind('<Left>', lambda e: self.show_previous_slice())
            master.bind('<Right>', lambda e: self.show_next_slice())

            # Create a frame for additional information
            self.info_frame = tk.Frame(master)
            self.info_frame.pack(fill=tk.X, padx=10, pady=5)

            # Add keyboard shortcut information
            self.shortcut_label = tk.Label(
                self.info_frame,
                text="Keyboard shortcuts: ← (Previous) | → (Next)",
                font=("Arial", 10),
                fg='gray'
            )
            self.shortcut_label.pack(pady=5)

            # Display first slice
            self.update_display()

        def update_display(self):
            """Update the displayed slice and counter."""
            # Update counter with current slice number
            self.counter_label.config(
                text=f"Slice {self.current_slice + 1} of {self.total_slices}"
            )

            # Clear and update the image
            self.ax.clear()
            self.ax.imshow(self.slices[self.current_slice], cmap='gray')
            self.ax.axis('off')
            
            # Update the title with slice information
            self.ax.set_title(f"Viewing Slice {self.current_slice + 1}/{self.total_slices}", 
                            pad=20, fontsize=12)
            
            self.canvas.draw()

            # Update button states and appearance
            if self.current_slice == 0:
                self.prev_button.config(state=tk.DISABLED, bg='gray')
            else:
                self.prev_button.config(state=tk.NORMAL, bg='#4a90e2')

            if self.current_slice == self.total_slices - 1:
                self.next_button.config(state=tk.DISABLED, bg='gray')
            else:
                self.next_button.config(state=tk.NORMAL, bg='#4a90e2')

        def show_previous_slice(self):
            """Display the previous slice if available."""
            if self.current_slice > 0:
                self.current_slice -= 1
                self.update_display()

        def show_next_slice(self):
            """Display the next slice if available."""
            if self.current_slice < self.total_slices - 1:
                self.current_slice += 1
                self.update_display()

    try:
        # Get the pixel array from the DICOM dataset
        slices = ds.pixel_array
        
        # Handle different dimensional data
        if len(slices.shape) == 2:  # Single slice
            slices = slices[np.newaxis, ...]  # Add dimension to make it 3D
        elif len(slices.shape) == 3:  # Multiple slices
            pass
        else:
            raise ValueError("Unsupported image dimensions")

        # Create the slice viewer
        viewer = SliceViewer(slice_window, slices)

        # Configure window closing
        def on_closing():
            plt.close(viewer.fig)  # Clean up matplotlib figure
            slice_window.destroy()

        slice_window.protocol("WM_DELETE_WINDOW", on_closing)

    except Exception as e:
        messagebox.showerror("Error", f"Error displaying slices: {str(e)}")
        slice_window.destroy()

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
        (0x8, 0x5),
        (0x8, 0x8),
        (0x8, 0x12),
        (0x8, 0x13),
        (0x8, 0x16),
        (0x8, 0x18),
        (0x8, 0x20),
        (0x8, 0x22),
        (0x8, 0x23),
        (0x8, 0x30),
        (0x8, 0x32),
        (0x8, 0x33),
        (0x8, 0x60),
        (0x8, 0x1030),
        (0x8, 0x1032),
        (0x8, 0x103e),
        (0x8, 0x1111),

    ],
    "Series Information": [
        (0x20, 0xd),
        (0x20, 0xe),
        (0x20, 0x11),
        (0x20, 0x13),
        (0x20, 0x32),
        (0x20, 0x37),
        (0x20, 0x52),
        (0x20, 0x1041),
        (0x20, 0x4000),
         #
    ],
    "Patient Information": [
        (0x0010, 0x0010),  # Patient's Name
        (0x0010, 0x0020),  # Patient ID
        (0x0010, 0x0030),  # Patient Birth Date
        (0x0010, 0x0040),  # Patient Sex
        (0x10, 0x1010),
    ],
    "Image Acquisition Parameters": [
        (0x18, 0x10),
        (0x18, 0x22),
        (0x18, 0x50),
        (0x18, 0x60),
        (0x18, 0x88),
        (0x18, 0x90),
        (0x18, 0x1030),
        (0x18, 0x1100),
        (0x18, 0x1120),
        (0x18, 0x1130),
        (0x18, 0x1140),
        (0x18, 0x1151),
        (0x18, 0x1152),
        (0x18, 0x1160),
        (0x18, 0x1210),
        (0x18, 0x5100),

    ],
    "Equipment Information": [
        (0x0008, 0x0070),  # Manufacturer
        (0x0018, 0x1000),  # Device Serial Number
        
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
        #"Clean Pixel Data"
        # Tags that may contain pixel data with identification information
        (0x0008, 0x0008),  # Image Type
        (0x0052, 0x0006),  # Procedure Code Sequence
    #"Clean Recognizable Visual Features"
        # Tags that may lead to visual identification of individuals
        (0x0010, 0x0010),  # Patient's Name
        (0x0010, 0x0020),  # Patient ID
        (0x0010, 0x0030),  # Patient Birth Date
        (0x0010, 0x0040),  # Patient Sex
        (0x0008, 0x0020),  # Study Date
        (0x0008, 0x0030),  # Study Time
        (0x0008, 0x0090),  # Referring Physician Name
        (0x0008, 0x0050),  # Accession Number
        (0x0010, 0x0024),  # Medical Record Number
    #"Clean Graphics"
        # Tags that may contain identification information encoded as graphics or text annotations
        (0x0008, 0x0070),  # Manufacturer
        (0x0018, 0x1000),  # Device Serial Number
    #"Clean Structured Content"
        # Tags that may contain structured report information
        (0x0054, 0x0220),  # View Position
        (0x0054, 0x0222),  # View Position Modifier
    #"Clean Descriptors"
        # Tags that contain descriptive information which may include sensitive data
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
    metadata_text = tk.Text(top_frame, height=5, wrap=tk.WORD)
    metadata_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    # Image display frame
    image_frame = tk.Frame(main_container)
    image_frame.pack(fill=tk.BOTH, expand=True)

    # Start the GUI event loop
    root.mainloop()
