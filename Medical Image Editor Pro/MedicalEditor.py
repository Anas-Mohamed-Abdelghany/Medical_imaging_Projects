import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QLabel, QMainWindow, QPushButton, QVBoxLayout,
    QHBoxLayout, QWidget, QFileDialog, QFrame, QComboBox,
    QDoubleSpinBox, QFormLayout, QGroupBox, QTextEdit, QSlider, QScrollArea, QMessageBox,
    QMenuBar, QAction, QDialog, QRadioButton, QButtonGroup
)
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor
from PyQt5.QtCore import Qt, QRect, QPoint
from pydicom.pixel_data_handlers.util import apply_modality_lut, apply_voi_lut
import pydicom
from PyQt5.QtWidgets import QSizePolicy
from pydicom.pixel_data_handlers.util import apply_windowing
from scipy.ndimage import zoom, gaussian_filter, uniform_filter
import random
from skimage import exposure, filters
import matplotlib.pyplot as plt  # Importing matplotlib for histogram plotting


class ClickableImageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selection_active = False
        self.selected_points = []
        self.selection_rect = None
        self.start_point = None
        self.current_point = None
        self.is_original = False  # Flag to identify the original image label

    def mousePressEvent(self, event):
        if self.selection_active and event.button() == Qt.LeftButton:
            self.start_point = event.pos()
            self.current_point = event.pos()
            self.selection_rect = QRect()
            self.update()

    def mouseMoveEvent(self, event):
        if self.selection_active and self.start_point is not None:
            self.current_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if self.selection_active and event.button() == Qt.LeftButton:
            if self.start_point and self.current_point:
                # Create QRect from points
                self.selection_rect = QRect(self.start_point, self.current_point)
                # Normalize the rectangle (ensure positive width/height)
                self.selection_rect = self.selection_rect.normalized()
                self.selected_points = [self.start_point, self.current_point]
                self.start_point = None
                self.current_point = None
                self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.selection_active:
            painter = QPainter(self)
            pen = QPen(QColor(255, 0, 0))  # Red color
            pen.setWidth(2)
            painter.setPen(pen)

            if self.start_point and self.current_point:
                rect = QRect(self.start_point, self.current_point).normalized()
                painter.drawRect(rect)
            elif self.selection_rect:
                painter.drawRect(self.selection_rect)

class SNRDisplay(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumHeight(100)
        self.setStyleSheet("""
            QTextEdit {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 5px;
            }
        """)

class CNRDisplay(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumHeight(100)
        self.setStyleSheet("""
            QTextEdit {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 5px;
            }
        """)

class ZoomDialog(QDialog):
    def __init__(self, image, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Zoom")
        self.resize(800, 600)

        # Store the original image
        self.original_image = image
        self.current_image = self.original_image.copy()
        self.zoom_factor = 1.0

        # Main layout
        self.main_layout = QVBoxLayout(self)

        # Image display layout
        self.display_layout = QHBoxLayout()

        # Image labels
        self.input_view = QLabel()
        self.output_view = QLabel()
        for view in [self.input_view, self.output_view]:
            view.setAlignment(Qt.AlignCenter)
            view.setStyleSheet(
                "border: 1px solid #cccccc; background-color: #f0f0f0;"
            )
            view.setMinimumSize(300, 300)

        self.display_layout.addWidget(self.input_view)
        self.display_layout.addWidget(self.output_view)

        # Controls layout
        self.controls_layout = QHBoxLayout()

        # Zoom controls
        self.zoom_group = QGroupBox("Zoom Controls")
        self.zoom_layout = QVBoxLayout(self.zoom_group)

        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(1, 500)  # Zoom range from 1% to 500%
        self.zoom_slider.setValue(100)
        self.zoom_slider.setTickPosition(QSlider.TicksBelow)
        self.zoom_slider.setTickInterval(10)
        self.zoom_slider.valueChanged.connect(self.update_zoom)

        self.zoom_label = QLabel("Zoom: 100%")
        self.zoom_layout.addWidget(self.zoom_slider)
        self.zoom_layout.addWidget(self.zoom_label)

        self.reset_button = QPushButton("Reset View")
        self.reset_button.clicked.connect(self.reset_view)
        self.zoom_layout.addWidget(self.reset_button)

        # Interpolation controls
        self.interp_group = QGroupBox("Interpolation Method")
        self.interp_layout = QVBoxLayout(self.interp_group)
        self.interpolation_dropdown = QComboBox()
        self.interpolation_dropdown.addItems([
            "Nearest Neighbor", "Linear", "Cubic",
            "Lanczos4", "Area"
        ])
        self.interpolation_dropdown.currentTextChanged.connect(self.apply_zoom)
        self.interp_layout.addWidget(self.interpolation_dropdown)

        # Apply and Close buttons
        self.apply_close_layout = QHBoxLayout()
        self.apply_button = QPushButton("Apply Zoom")
        self.apply_button.clicked.connect(self.apply_and_close)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        self.apply_close_layout.addWidget(self.apply_button)
        self.apply_close_layout.addWidget(self.close_button)

        # Add controls to controls layout
        self.controls_layout.addWidget(self.zoom_group)
        self.controls_layout.addWidget(self.interp_group)

        # Add layouts to main layout
        self.main_layout.addLayout(self.display_layout)
        self.main_layout.addLayout(self.controls_layout)
        self.main_layout.addLayout(self.apply_close_layout)

        # Display the images
        self.display_image(self.original_image, self.input_view)
        self.display_image(self.current_image, self.output_view)

    def display_image(self, image, view):
        if len(image.shape) == 2:
            # Grayscale image
            height, width = image.shape
            bytes_per_line = width
            q_image = QImage(
                image.data, width, height,
                bytes_per_line, QImage.Format_Grayscale8
            )
        else:
            # RGB image
            height, width, channel = image.shape
            bytes_per_line = 3 * width
            q_image = QImage(
                image.data, width, height,
                bytes_per_line, QImage.Format_RGB888
            )
            q_image = q_image.rgbSwapped()
        pixmap = QPixmap.fromImage(q_image)
        view.setPixmap(pixmap)

    def update_zoom(self):
        slider_value = self.zoom_slider.value()
        self.zoom_factor = slider_value / 100.0
        self.zoom_label.setText(f"Zoom: {slider_value}%")
        self.apply_zoom()

    def apply_zoom(self):
        methods = {
            "Nearest Neighbor": cv2.INTER_NEAREST,
            "Linear": cv2.INTER_LINEAR,
            "Cubic": cv2.INTER_CUBIC,
            "Lanczos4": cv2.INTER_LANCZOS4,
            "Area": cv2.INTER_AREA
        }
        interpolation = methods.get(
            self.interpolation_dropdown.currentText(), cv2.INTER_LINEAR
        )
        new_width = int(self.original_image.shape[1] * self.zoom_factor)
        new_height = int(self.original_image.shape[0] * self.zoom_factor)
        if new_width > 0 and new_height > 0:
            self.current_image = cv2.resize(
                self.original_image, (new_width, new_height), interpolation=interpolation
            )
            self.display_image(self.current_image, self.output_view)
        else:
            QMessageBox.warning(self, "Warning", "Zoom level too low.")

    def reset_view(self):
        self.zoom_slider.setValue(100)
        self.display_image(self.original_image, self.output_view)

    def apply_and_close(self):
        # Here you can process the zoomed image if needed
        self.accept()

class DicomImageEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DICOM Image Editor with Zoom")
        self.resize(1400, 800)
        self.dicom_data = None
        self.original_pixel_array = None
        self.processing_history = []
        self.selected_area = None
        self.selected_reference = None
        self.selected_2nd = None
        self.zoom_factor = 1.0
        self.edit_display_count = 0
        self.contrast_toggle = 0  # Add this line to track the toggle state
        self.all_toggle = 0
        self.FOV_toggle = 0
        self.setup_ui()

    def normalize_to_uint8(self, image):
        """Normalize image to uint8 format."""
        try:
            if image.dtype == np.uint8:
                return image
                
            # Get the minimum and maximum values
            min_val = np.min(image)
            max_val = np.max(image)
            
            # Avoid division by zero
            if max_val == min_val:
                return np.zeros_like(image, dtype=np.uint8)
            
            # Normalize to 0-255 range
            normalized = ((image - min_val) * 255.0 / (max_val - min_val))
            
            # Convert to uint8
            return normalized.astype(np.uint8)
        except Exception as e:
            print(f"Error in normalize_to_uint8: {e}")
            return None

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Create a scroll area for the sidebar
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)  # Allow the scroll area to resize with the window
        scroll_area.setFixedWidth(350)  # Set a fixed width for the scroll area
        scroll_area.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        # Menu bar
        menubar = self.menuBar()
        zoom_menu = menubar.addMenu('Zoom')

        # Zoom action
        zoom_action = QAction('Open Zoom Tool', self)
        zoom_action.triggered.connect(self.open_zoom_dialog)
        zoom_menu.addAction(zoom_action)
        
        # Sidebar widget
        sidebar = QWidget()
        self.sidebar_layout = QVBoxLayout(sidebar)

        # Import button
        self.import_button = QPushButton("Import DICOM")
        self.import_button.clicked.connect(self.load_image)
        self.sidebar_layout.addWidget(self.import_button)

        # Add the "Load Standard Image" button
        self.load_image_button = QPushButton("Load Image")
        self.load_image_button.clicked.connect(self.load_standard_image)
        self.sidebar_layout.addWidget(self.load_image_button)

        self.clear_button = QPushButton("Clear Results")
        self.clear_button.clicked.connect(self.clear_results)  # This line remains unchanged
        self.sidebar_layout.addWidget(self.clear_button)

        # Add Save buttons
        self.save_button1 = QPushButton("Save Image 1")
        self.save_button1.clicked.connect(lambda: self.save_image(self.edited_image_label1))
        self.sidebar_layout.addWidget(self.save_button1)

        self.save_button2 = QPushButton("Save Image 2")
        self.save_button2.clicked.connect(lambda: self.save_image(self.edited_image_label2))
        self.sidebar_layout.addWidget(self.save_button2)

        # FOV Calculator Group
        fov_group = QGroupBox("Field of View Calculator")
        fov_layout = QVBoxLayout()

        self.constant_param = QComboBox()
        self.constant_param.addItems(["FOV", "Pixels", "Resolution"])
        fov_layout.addWidget(self.constant_param)

        # Input fields with form layout
        form_layout = QFormLayout()

        self.fov_input = QDoubleSpinBox()
        self.fov_input.setRange(0.1, 1000)  # Adjust range as needed
        self.fov_input.setValue(100.0)  # Set default value
        self.fov_input.setSuffix(" mm")
        form_layout.addRow("FOV:", self.fov_input)

        self.pixels_input = QDoubleSpinBox()
        self.pixels_input.setRange(1, 10000)  # Adjust range as needed
        self.pixels_input.setValue(512.0)  # Set default value
        self.pixels_input.setSuffix(" px")
        form_layout.addRow("Pixels:", self.pixels_input)

        self.resolution_input = QDoubleSpinBox()
        self.resolution_input.setRange(0.1, 10)  # Adjust range as needed
        self.resolution_input.setValue(1.0)  # Set default value
        self.resolution_input.setSuffix(" mm/px")
        form_layout.addRow("Resolution:", self.resolution_input)

        fov_layout.addLayout(form_layout)

        # Add Apply Changes button
        self.apply_changes_button = QPushButton("Apply Changes")
        self.apply_changes_button.clicked.connect(self.apply_fov_changes)
        fov_layout.addWidget(self.apply_changes_button)

        fov_group.setLayout(fov_layout)
        self.sidebar_layout.addWidget(fov_group)

        # Signal Analysis Group
        signal_group = QGroupBox("Signal Analysis")
        signal_layout = QVBoxLayout()

        self.select_area_button = QPushButton("Select Area")
        self.select_area_button.clicked.connect(self.start_area_selection)
        signal_layout.addWidget(self.select_area_button)

        self.select_reference_button = QPushButton("Select Reference")
        self.select_reference_button.clicked.connect(self.start_reference_selection)
        signal_layout.addWidget(self.select_reference_button)

        self.select_2nd_button = QPushButton("Select Second")
        self.select_2nd_button.clicked.connect(self.start_2nd_selection)
        signal_layout.addWidget(self.select_2nd_button)

        self.confirm_selection_button = QPushButton("Confirm Selection")
        self.confirm_selection_button.clicked.connect(self.confirm_selection)
        self.confirm_selection_button.hide()
        signal_layout.addWidget(self.confirm_selection_button)

        # Show SNR button
        self.show_snr_button = QPushButton("Show SNR")
        self.show_snr_button.clicked.connect(self.show_SNR)
        signal_layout.addWidget(self.show_snr_button)

        # Show CNR button
        self.show_cnr_button = QPushButton("Show CNR")
        self.show_cnr_button.clicked.connect(self.show_CNR)
        signal_layout.addWidget(self.show_cnr_button)

        # Add SNR display
        self.snr_display = QTextEdit()
        self.snr_display.setReadOnly(True)
        self.snr_display.setMaximumHeight(100)
        self.snr_display.setPlaceholderText("SNR calculation results will appear here...")
        signal_layout.addWidget(self.snr_display)

        # Add CNR display
        self.cnr_display = QTextEdit()
        self.cnr_display.setReadOnly(True)
        self.cnr_display.setMaximumHeight(100)
        self.cnr_display.setPlaceholderText("CNR calculation results will appear here...")
        signal_layout.addWidget(self.cnr_display)

        signal_group.setLayout(signal_layout)
        self.sidebar_layout.addWidget(signal_group)

        # Filter Application Group
        filter_group = QGroupBox("Low/High-Pass Application")
        filter_layout = QVBoxLayout()

        # Lowpass filter controls
        self.lowpass_combo = QComboBox()
        self.lowpass_combo.addItems(["Select Lowpass Filter", "Gaussian", "Mean"])
        filter_layout.addWidget(QLabel("Lowpass Filter:"))
        filter_layout.addWidget(self.lowpass_combo)

        # Highpass filter controls
        self.highpass_combo = QComboBox()
        self.highpass_combo.addItems(["Select Highpass Filter", "Laplacian", "Sobel"])
        filter_layout.addWidget(QLabel("Highpass Filter:"));
        filter_layout.addWidget(self.highpass_combo)

        self.power_slider = QSlider(Qt.Horizontal)
        self.power_slider.setRange(1, 10)  # Adjust range as needed
        self.power_slider.setValue(1)  # Default value
        filter_layout.addWidget(QLabel("Filter Power:"))
        filter_layout.addWidget(self.power_slider)

        self.apply_filter_button = QPushButton("Apply Filters")
        self.apply_filter_button.clicked.connect(self.apply_filters)
        filter_layout.addWidget(self.apply_filter_button)

        filter_group.setLayout(filter_layout)
        self.sidebar_layout.addWidget(filter_group)

        # Histogram Selection
        histogram_group = QGroupBox("Histogram")
        histogram_layout = QVBoxLayout()
        self.histogram_selector = QComboBox()
        self.histogram_selector.addItems(["Select Image for Histogram", "Original Image", "Edited Image 1", "Edited Image 2"])
        histogram_layout.addWidget(self.histogram_selector)

        # Histogram button
        self.show_histogram_button = QPushButton("Show Histogram")
        self.show_histogram_button.clicked.connect(self.show_histogram)
        histogram_layout.addWidget(self.show_histogram_button)

        histogram_group.setLayout(histogram_layout)
        self.sidebar_layout.addWidget(histogram_group)

        # Add stretch to push buttons to top
        self.sidebar_layout.addStretch()

        # Set the sidebar as the widget for the scroll area
        scroll_area.setWidget(sidebar)

        # Add the sidebar to the scroll area
        scroll_area.setWidget(sidebar)

        self.setup_contrast_adjustment()

        # Main content area
        content_layout = QHBoxLayout()

        # Add widgets to the main layout with stretch factors
        main_layout.addWidget(scroll_area, stretch=0)
        main_layout.addLayout(content_layout, stretch=1)
        
        # Original image section
        original_section = QVBoxLayout()
        self.original_image_label = ClickableImageLabel()
        self.original_image_label.is_original = True  # Set flag for original image
        self.original_image_label.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.original_image_label.setAlignment(Qt.AlignCenter)
        self.original_image_label.setFixedSize(400, 400)  # Set fixed size
        original_section.addWidget(self.original_image_label)
        content_layout.addLayout(original_section)

        # Right side images with calculation displays
        right_layout = QVBoxLayout()

        # First edited image section
        edit1_section = QVBoxLayout()
        self.edited_image_label1 = ClickableImageLabel()
        self.edited_image_label1.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.edited_image_label1.setAlignment(Qt.AlignCenter)
        self.edited_image_label1.setFixedSize(400, 400)  # Set fixed size
        edit1_section.addWidget(self.edited_image_label1)
        right_layout.addLayout(edit1_section)

        # Second edited image section
        edit2_section = QVBoxLayout()
        self.edited_image_label2 = ClickableImageLabel()
        self.edited_image_label2.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.edited_image_label2.setAlignment(Qt.AlignCenter)
        self.edited_image_label2.setFixedSize(400, 400)  # Set fixed size
        edit2_section.addWidget(self.edited_image_label2)
        right_layout.addLayout(edit2_section)

        content_layout.addLayout(right_layout)

        # Add layouts to main layout
        main_layout.addLayout(content_layout)

        # Initialize states
        self.constant_param.currentIndexChanged.connect(self.update_calculator_state)
        self.update_calculator_state()

        # Call to setup noise application UI
        self.setup_noise_application()
        # Call to setup denoising UI
        self.setup_denoising()

    def save_image_as_dicom(self, edited_image_label):
        """Save the edited image as a DICOM file with original metadata."""
        # Check if an image is available in the label
        if edited_image_label.pixmap() is None:
            QMessageBox.warning(self, "Warning", "No image to save.")
            return

        # Check if original DICOM data exists
        if self.dicom_data is None:
            QMessageBox.warning(self, "Warning", "No original DICOM metadata available.")
            return

        # Convert the pixmap to a numpy array
        pixmap = edited_image_label.pixmap()
        image_array = self.convert_pixmap_to_numpy(pixmap)

        if image_array is None:
            QMessageBox.warning(self, "Warning", "Could not convert image.")
            return

        # Open file dialog to choose save location
        file_dialog_result = QFileDialog.getSaveFileName(
            self, 
            "Save DICOM File", 
            "", 
            "DICOM Files (*.dcm)"
        )
        
        # Unpack safely
        if len(file_dialog_result) > 0:
            file_path = file_dialog_result[0]
        else:
            return  # User cancelled

        # Ensure file path ends with .dcm
        if not file_path.lower().endswith('.dcm'):
            file_path += '.dcm'

        try:
            # Ensure the image is in the correct format for DICOM
            # Handle multi-dimensional arrays
            if len(image_array.shape) > 2:
                # If it's a color image, convert to grayscale
                if image_array.shape[2] == 3:
                    image_array = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
                elif image_array.shape[2] == 4:
                    image_array = cv2.cvtColor(image_array, cv2.COLOR_RGBA2GRAY)

            # Ensure the image matches the original pixel array type and shape
            original_array = self.original_pixel_array

            # If the edited image is a different size, resize to match original
            if image_array.shape != original_array.shape:
                # Resize the image to match the original dimensions
                image_array = cv2.resize(
                    image_array, 
                    (original_array.shape[1], original_array.shape[0]), 
                    interpolation=cv2.INTER_LINEAR
                )

            # Ensure the image is in the same data type as the original
            if original_array.dtype != image_array.dtype:
                # If original was uint16, convert edited image to uint16
                if original_array.dtype == np.uint16:
                    # Normalize and convert to uint16
                    image_array = ((image_array / image_array.max()) * 65535).astype(np.uint16)
                else:
                    # Fallback conversion
                    image_array = image_array.astype(original_array.dtype)

            # Create a deep copy of the original dataset
            new_dataset = pydicom.Dataset()

            # Copy all elements from the original dataset
            for elem in self.dicom_data:
                # Skip PixelData and some dynamic attributes
                if elem.tag not in [
                    (0x7FE0, 0x0010),  # PixelData
                    (0x0008, 0x0018),  # SOP Instance UID
                    (0x0020, 0x000D),  # Study Instance UID
                    (0x0020, 0x000E),  # Series Instance UID
                ]:
                    new_dataset.add(elem)

            # Ensure pixel data matches original specifications
            # Calculate expected pixel data size
            bits_allocated = self.dicom_data.get('BitsAllocated', 16)
            samples_per_pixel = self.dicom_data.get('SamplesPerPixel', 1)
            
            # Ensure image array matches original specifications
            if bits_allocated == 16:
                image_array = image_array.astype(np.uint16)
            else:
                image_array = image_array.astype(np.uint8)

            # Update key attributes
            new_dataset.PixelData = image_array.tobytes()
            new_dataset.Rows = image_array.shape[0]
            new_dataset.Columns = image_array.shape[1]
            
            # Copy critical image-related attributes
            image_tags = [
                (0x0028, 0x0100),  # BitsAllocated
                (0x0028, 0x0101),  # BitsStored
                (0x0028, 0x0102),  # HighBit
                (0x0028, 0x0103),  # PixelRepresentation
                (0x0028, 0x0002),  # SamplesPerPixel
                (0x0028, 0x0004),  # PhotometricInterpretation
            ]
            
            for tag in image_tags:
                if tag in self.dicom_data:
                    new_dataset.add(self.dicom_data[tag])

            # Regenerate UIDs to ensure uniqueness
            new_dataset.SOPInstanceUID = pydicom.uid.generate_uid()
            new_dataset.StudyInstanceUID = pydicom.uid.generate_uid()
            new_dataset.SeriesInstanceUID = pydicom.uid.generate_uid()

            # Create file meta information
            file_meta = pydicom.Dataset()
            file_meta.MediaStorageSOPClassUID = pydicom.uid.CTImageStorage
            file_meta.MediaStorageSOPInstanceUID = new_dataset.SOPInstanceUID
            file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian

            # Create FileDataset
            file_dataset = pydicom.FileDataset(
                file_path, 
                new_dataset, 
                file_meta=file_meta
            )

            # Set specific attributes to match original image characteristics
            file_dataset.is_little_endian = True
            file_dataset.is_implicit_VR = False

            # Save the new DICOM file
            pydicom.dcmwrite(file_path, file_dataset, write_like_original=False)
            
            # Debug information
            print(f"Original image shape: {original_array.shape}")
            print(f"Saved image shape: {image_array.shape}")
            print(f"Original image dtype: {original_array.dtype}")
            print(f"Saved image dtype: {image_array.dtype}")
            print(f"Pixel data size: {len(image_array.tobytes())} bytes")
            
            QMessageBox.information(self, "Success", f"Image saved as DICOM file:\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save DICOM file: {str(e)}")
            import traceback
            traceback.print_exc()  
        
    def show_histogram(self):
        """Show the histogram of the selected image."""
        selected_image = self.histogram_selector.currentText()
        
        # Determine which image to display
        if selected_image == "Original Image":
            image_to_show = self.original_pixel_array
        elif selected_image == "Edited Image 1":
            pixmap = self.edited_image_label1.pixmap()
            image_to_show = self.convert_pixmap_to_numpy(pixmap) if pixmap is not None else None
        elif selected_image == "Edited Image 2":
            pixmap = self.edited_image_label2.pixmap()
            image_to_show = self.convert_pixmap_to_numpy(pixmap) if pixmap is not None else None
        else:
            return

        if image_to_show is not None:
            # Ensure the image is in uint8 format
            if image_to_show.dtype == np.uint16:
                image_to_show = ((image_to_show / 65535) * 255).astype(np.uint8)
            elif image_to_show.dtype != np.uint8:
                image_to_show = image_to_show.astype(np.uint8)

            # Flatten the image for histogram
            if len(image_to_show.shape) == 3:
                # If it's a color image, convert to grayscale
                if image_to_show.shape[2] == 3:
                    image_to_show = cv2.cvtColor(image_to_show, cv2.COLOR_RGB2GRAY)
                elif image_to_show.shape[2] == 4:
                    image_to_show = cv2.cvtColor(image_to_show, cv2.COLOR_RGBA2GRAY)

            # Flatten the image
            histogram_data = image_to_show.flatten()

            # Plot the histogram
            plt.figure("Histogram")
            plt.clf()  # Clear the current figure
            plt.hist(histogram_data, bins=256, range=[0, 255], color='gray')
            plt.title(f"{selected_image} Histogram")
            plt.xlabel("Pixel Intensity")
            plt.ylabel("Frequency")
            plt.ylim([0, 2000])  # Minimized y-axis values
            plt.xlim([0, 255])
            plt.tight_layout()
            plt.show(block=False)
            plt.pause(0.1)  # Small pause to render the plot

    def convert_pixmap_to_numpy(self, pixmap):
        """
        Convert a QPixmap to a NumPy array.
        
        :param pixmap: QPixmap to convert
        :return: NumPy array representation of the image
        """
        if pixmap is None:
            return None

        # Convert QPixmap to QImage
        qimage = pixmap.toImage()
        
        # Get image dimensions
        width = qimage.width()
        height = qimage.height()
        
        # Convert QImage to NumPy array based on format
        ptr = qimage.bits()
        ptr.setsize(qimage.byteCount())
        
        # Handle different image formats
        if qimage.format() == QImage.Format_Grayscale8:
            return np.array(ptr).reshape((height, width))
        
        elif qimage.format() in [QImage.Format_RGB888, QImage.Format_RGBX8888]:
            # RGB image (3 channels)
            return np.array(ptr).reshape((height, width, 3))
        
        elif qimage.format() == QImage.Format_RGBA8888:
            # RGBA image (4 channels)
            return np.array(ptr).reshape((height, width, 4))
        
        else:
            # Fallback: try to convert to RGB
            qimage = qimage.convertToFormat(QImage.Format_RGB888)
            ptr = qimage.bits()
            ptr.setsize(qimage.byteCount())
            return np.array(ptr).reshape((height, width, 3))
        
    def setup_contrast_adjustment(self):
        contrast_group = QGroupBox("Contrast Adjustment")
        contrast_layout = QVBoxLayout()

        self.contrast_combo = QComboBox()
        self.contrast_combo.addItems([
            "Select Contrast Adjustment",
            "Histogram Equalization",
            "CLAHE",
            "Gamma Correction"
        ])
        contrast_layout.addWidget(self.contrast_combo)

        self.apply_contrast_button = QPushButton("Apply Contrast Adjustment")
        self.apply_contrast_button.clicked.connect(self.apply_contrast_adjustment)
        contrast_layout.addWidget(self.apply_contrast_button)

        contrast_group.setLayout(contrast_layout)
        self.sidebar_layout.addWidget(contrast_group)

    def apply_zoom(self):
        if self.original_pixel_array is None:
            return

        # Calculate new dimensions
        new_width = int(self.original_pixel_array.shape[1] * self.zoom_factor)
        new_height = int(self.original_pixel_array.shape[0] * self.zoom_factor)

        if new_width > 0 and new_height > 0:
            # Resize the image
            self.current_image = cv2.resize(
                self.original_pixel_array, (new_width, new_height), interpolation=cv2.INTER_LINEAR
            )
            self.show_image(self.original_image_label, self.current_image)
        else:
            QMessageBox.warning(self, "Warning", "Zoom level too low.")

    def apply_filters(self):
        """Apply selected filters to the original image."""
        if self.original_pixel_array is None:
            QMessageBox.warning(self, "Warning", "No image loaded.")
            return

        filtered_image = self.original_pixel_array.copy()

        # Apply lowpass filter
        lowpass_filter = self.lowpass_combo.currentText()
        lowpass_power = self.power_slider.value()

        if lowpass_filter == "Gaussian":
            filtered_image = gaussian_filter(filtered_image, sigma=lowpass_power)
        elif lowpass_filter == "Mean":
            filtered_image = uniform_filter(filtered_image, size=lowpass_power)

        self.show_image(self.edited_image_label1, filtered_image)  # Show lowpass filtered image in edited_image_label1

        # Apply highpass filter
        highpass_filter = self.highpass_combo.currentText()

        if highpass_filter == "Laplacian":
            try:
                filtered_image = filters.laplace(filtered_image)
            except ValueError:
                QMessageBox.warning(self, "Warning", "Could not apply Laplacian filter with the selected kernel size.")
                return
        elif highpass_filter == "Sobel":
            try:
                filtered_image = filters.sobel(filtered_image)
            except ValueError:
                QMessageBox.warning(self, "Warning", "Could not apply Sobel filter.")
                return

        # Normalize highpass result
        filtered_image = (filtered_image - filtered_image.min()) / (filtered_image.max() - filtered_image.min()) * 255
        filtered_image = filtered_image.astype(np.uint8)

        self.show_image(self.edited_image_label2, filtered_image)  # Show highpass filtered image in edited_image_label2       

    def update_zoom(self):
        slider_value = self.zoom_slider.value()
        self.zoom_factor = slider_value / 1000.0  # Assuming the slider value ranges from 100 to 10000
        self.zoom_label.setText(f"Zoom: {int(self.zoom_factor * 100)}%")
        self.apply_zoom()

    def setup_noise_application(self):
        noise_group = QGroupBox("Noise Application")
        noise_layout = QVBoxLayout()

        self.noise_combo = QComboBox()
        self.noise_combo.addItems(["Select Noise", "Gaussian Noise", "Salt and Pepper Noise", "Poisson"])
        noise_layout.addWidget(self.noise_combo)

        # Add a fixed slider for noise degree
        self.noise_degree_slider = QSlider(Qt.Horizontal)
        self.noise_degree_slider.setRange(0, 100)  # Adjust range as needed
        self.noise_degree_slider.setValue(25)  # Default value
        noise_layout.addWidget(QLabel("Noise Degree:"))
        noise_layout.addWidget(self.noise_degree_slider)

        self.apply_noise_button = QPushButton("Apply Noise")
        self.apply_noise_button.clicked.connect(self.apply_noise)
        noise_layout.addWidget(self.apply_noise_button)

        noise_group.setLayout(noise_layout)
        self.sidebar_layout.addWidget(noise_group)
    
    def open_zoom_dialog(self):
        """Open the zoom dialog window."""
        if self.original_pixel_array is None:
            QMessageBox.warning(self, "Warning", "No image loaded to zoom.")
            return
        # Prepare the image for zooming
        image = self.original_pixel_array.copy()
        if image.dtype != np.uint8:
            # Normalize image to 0-255 and convert to uint8
            min_val = image.min()
            max_val = image.max()
            if max_val > min_val:
                image = ((image - min_val) * 255 / (max_val - min_val)).astype(np.uint8)
            else:
                image = np.zeros_like(image, dtype=np.uint8)

        # Handle grayscale and color images
        if len(image.shape) == 2:
            # Grayscale image
            pass
        elif len(image.shape) == 3 and image.shape[2] == 3:
            # Color image, ensure it's in RGB format
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            QMessageBox.warning(self, "Warning", "Unsupported image format for zooming.")
            return

        zoom_dialog = ZoomDialog(image, self)
        if zoom_dialog.exec_() == QDialog.Accepted:
            # If user clicks "Apply Zoom", update the original image label
            self.original_pixel_array = zoom_dialog.current_image
            self.show_image(self.original_image_label, self.original_pixel_array)

    def setup_denoising(self):
        denoising_group = QGroupBox("Denoising Techniques")
        denoising_layout = QVBoxLayout()

        self.denoising_combo = QComboBox()
        self.denoising_combo.addItems(["Select Denoising", "Gaussian Filter", "Median Filter", "Bilateral Filter"])
        denoising_layout.addWidget(self.denoising_combo)

        self.apply_denoising_button = QPushButton("Apply Denoising")
        self.apply_denoising_button.clicked.connect(self.apply_denoising)
        denoising_layout.addWidget(self.apply_denoising_button)

        denoising_group.setLayout(denoising_layout)
        self.sidebar_layout.addWidget(denoising_group)

    def apply_denoising(self):
        """Apply selected denoising technique to the noisy image."""
        if self.edited_image_label1.pixmap() is None:
            print("No noisy image to denoise.")
            return

        # Convert QPixmap to QImage
        pixmap = self.edited_image_label1.pixmap()
        qimage = pixmap.toImage().convertToFormat(QImage.Format_Grayscale8)

        # Extract data as a numpy array
        width = qimage.width()
        height = qimage.height()
        ptr = qimage.bits()
        ptr.setsize(qimage.byteCount())
        noisy_image = np.array(ptr).reshape((height, width))

        denoising_type = self.denoising_combo.currentText()

        # Normalize the image if necessary
        noisy_image = noisy_image.astype(np.float32) / 255.0

        if denoising_type == "Gaussian Filter":
            denoised_image = gaussian_filter(noisy_image, sigma=2)

        elif denoising_type == "Median Filter":
            from scipy.ndimage import median_filter
            denoised_image = median_filter(noisy_image, size=3)

        elif denoising_type == "Bilateral Filter":
            from skimage.restoration import denoise_bilateral
            # Apply bilateral filter
            denoised_image = denoise_bilateral(noisy_image, sigma_color=0.05, sigma_spatial=15)

        # Convert back to [0, 255] for display
        denoised_image = np.clip(denoised_image * 255, 0, 255).astype(np.uint8)

        self.show_image(self.edited_image_label2, denoised_image)

    def apply_noise(self):
        """Apply selected noise to the original image."""
        if self.original_pixel_array is None:
            print("No original image loaded.")
            return

        noise_type = self.noise_combo.currentText()
        noisy_image = self.original_pixel_array.copy()

        # Get the degree of noise from the slider
        noise_degree = self.noise_degree_slider.value()  # Get the slider value

        if noise_type == "Gaussian Noise":
            mean = 0
            std_dev = noise_degree / 100.0 * 255  # Adjusted to scale noise based on slider value
            gaussian_noise = np.random.normal(mean, std_dev, noisy_image.shape).astype(np.float32)
            noisy_image = self.original_pixel_array.astype(np.float32) + gaussian_noise
            noisy_image = np.clip(noisy_image, 0, 255).astype(np.uint8)

        elif noise_type == "Salt and Pepper Noise":
            s_vs_p = 0.5
            amount = noise_degree / 100.0  # Convert slider value to a percentage
            out = np.copy(noisy_image)
            # Salt mode
            num_salt = np.ceil(amount * noisy_image.size * s_vs_p)
            coords = [np.random.randint(0, i - 1, int(num_salt)) for i in noisy_image.shape]
            out[tuple(coords)] = 255  # Set salt pixels to white

            # Pepper mode
            num_pepper = np.ceil(amount * noisy_image.size * (1. - s_vs_p))
            coords = [np.random.randint(0, i - 1, int(num_pepper)) for i in noisy_image.shape]
            out[tuple(coords)] = 0  # Set pepper pixels to black
            noisy_image = out

        elif noise_type == "Poisson":
            snr = (100 - noise_degree) / 100.0  # Reverse scale noise based on slider value
            noisy = np.random.poisson(self.original_pixel_array / 255.0 * snr) / snr
            noisy_image = np.clip(noisy * 255, 0, 255).astype(np.uint8)

        self.show_image(self.edited_image_label1, noisy_image)

    def apply_contrast_adjustment(self):
        """Apply selected contrast adjustment to the original image."""
        if self.original_pixel_array is None:
            QMessageBox.warning(self, "Warning", "No image loaded.")
            return

        contrast_type = self.contrast_combo.currentText()
        if contrast_type == "Select Contrast Adjustment":
            QMessageBox.warning(self, "Warning", "Please select a contrast adjustment method.")
            return

        adjusted_image = self.original_pixel_array.copy()

        # Check the original image data type and range
        print(f"Original image dtype: {adjusted_image.dtype}, min: {adjusted_image.min()}, max: {adjusted_image.max()}")

        # Normalize the image to [0, 1] for processing
        min_val = adjusted_image.min()
        max_val = adjusted_image.max()
        if max_val > min_val:
            adjusted_image = (adjusted_image - min_val) / (max_val - min_val)
        else:
            adjusted_image = np.zeros_like(adjusted_image, dtype=np.float32)

        if contrast_type == "Histogram Equalization":
            from skimage import exposure
            adjusted_image = exposure.equalize_hist(adjusted_image)

        elif contrast_type == "CLAHE":
            from skimage import exposure
            adjusted_image = exposure.equalize_adapthist(adjusted_image, clip_limit=0.03)

        elif contrast_type == "Gamma Correction":
            gamma_value = 1.5  # You can make this adjustable by adding a slider or input field
            adjusted_image = np.power(adjusted_image, gamma_value)

        # Convert back to [0, 255] for display
        adjusted_image = np.clip(adjusted_image * 255, 0, 255).astype(np.uint8)

        # Use the toggle state to determine which edit box to update 
        if self.contrast_toggle == 0: 
            self.show_image(self.edited_image_label1, adjusted_image) 
            self.contrast_toggle = 1  # Toggle to the next edit box 
        else: 
            self.show_image(self.edited_image_label2, adjusted_image) 
            self.contrast_toggle = 0  # Toggle back to the first edit box

    def auto_calculate(self):
        """Automatically calculate values when inputs change."""
        try:
            constant = self.constant_param.currentText()
            pixels = self.pixels_input.value()
            
            if constant == "FOV":
                fov = self.fov_input.value()
                resolution = fov / pixels if pixels != 0 else 0
                self.resolution_input.blockSignals(True)
                self.resolution_input.setValue(resolution)
                self.resolution_input.blockSignals(False)
            elif constant == "Pixels":
                resolution = self.resolution_input.value()
                fov = pixels * resolution
                self.fov_input.blockSignals(True)
                self.fov_input.setValue(fov)
                self.fov_input.blockSignals(False)
            elif constant == "Resolution":
                resolution = self.resolution_input.value()
                fov = pixels * resolution
                self.fov_input.blockSignals(True)
                self.fov_input.setValue(fov)
                self.fov_input.blockSignals(False)

        except Exception as e:
            print(f"Error in calculation: {e}")
            
    def apply_fov_changes(self):
        """Adjust the Field of View (FOV) and display in the selected viewport without cropping."""
        if self.original_pixel_array is None:
            print("No image loaded to apply FOV changes")
            return

        try:
            # Get current FOV calculator values
            scale = max(1, int(self.pixels_input.value()))
            base_image = self.original_pixel_array[::scale, ::scale]

            # Normalize the image to uint8 format
            base_image_uint8 = ((base_image - np.min(base_image)) * (255.0 / (np.max(base_image) - np.min(base_image)))).astype(np.uint8)

            # Calculate dimensions
            h, w = base_image.shape
            pixel_size = self.pixels_input.value()

            # Calculate the initial limits for the zoomed region (centered FOV)
            x_start = max(0, (w - pixel_size) // 2)
            y_start = max(0, (h - pixel_size) // 2)
            x_end = min(w, x_start + pixel_size)
            y_end = min(h, y_start + pixel_size)

            # Add to processing history
            self.processing_history.append(("fov_calculation", {
                "scale": scale,
                "pixel_size": pixel_size,
                "x_range": (x_start, x_end),
                "y_range": (y_start, y_end)
            }))

            # Use the toggle state to determine which edit box to update
            if self.FOV_toggle == 0:
                self.show_image(self.edited_image_label1, base_image_uint8)
                self.FOV_toggle = 1  # Toggle to the next edit box
            else:
                self.show_image(self.edited_image_label2, base_image_uint8)
                self.FOV_toggle = 0  # Toggle back to the first edit box

            print("FOV changes applied and image updated")

        except Exception as e:
            print(f"Error applying FOV changes: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"An error occurred while applying FOV changes: {e}")

    def update_calculator_state(self):
        """Update which parameters are editable based on the constant selection."""
        constant = self.constant_param.currentText()
        self.fov_input.setEnabled(constant != "FOV")
        self.pixels_input.setEnabled(constant != "Pixels")
        self.resolution_input.setEnabled(constant != "Resolution")
        self.auto_calculate()
    
    def start_area_selection(self):
        """Start area selection mode."""
        # Create a dialog to choose the image for selection
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Image for Area")
        layout = QVBoxLayout()

        # Radio buttons for image selection
        button_group = QButtonGroup()
        original_radio = QRadioButton("Original Image")
        edited1_radio = QRadioButton("Edited Image 1")
        edited2_radio = QRadioButton("Edited Image 2")
        
        button_group.addButton(original_radio)
        button_group.addButton(edited1_radio)
        button_group.addButton(edited2_radio)
        
        original_radio.setChecked(True)

        layout.addWidget(original_radio)
        layout.addWidget(edited1_radio)
        layout.addWidget(edited2_radio)

        # Confirm button
        confirm_button = QPushButton("Select")
        confirm_button.clicked.connect(dialog.accept)

        layout.addWidget(confirm_button)
        dialog.setLayout(layout)

        # Show the dialog
        if dialog.exec_() == QDialog.Accepted:
            # Determine which image to use for selection
            if original_radio.isChecked():
                selection_label = self.original_image_label
            elif edited1_radio.isChecked():
                selection_label = self.edited_image_label1
            else:
                selection_label = self.edited_image_label2

            # Deactivate selection on all labels
            self.original_image_label.selection_active = False
            self.edited_image_label1.selection_active = False
            self.edited_image_label2.selection_active = False

            # Activate selection mode on the chosen label
            selection_label.selection_active = True
            selection_label.selected_points = []
            selection_label.selection_rect = None
            
            # Store the current selection label
            self.current_selection_label = selection_label
            
            self.confirm_selection_button.show()
            self.select_area_button.setEnabled(False)
            self.select_reference_button.setEnabled(False)
            self.select_2nd_button.setEnabled(False)

            # Force update to ensure the red selection box is drawn
            selection_label.update()

    def start_reference_selection(self):
        """Start reference selection mode."""
        # Create a dialog to choose the image for selection
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Image for Reference")
        layout = QVBoxLayout()

        # Radio buttons for image selection
        button_group = QButtonGroup()
        original_radio = QRadioButton("Original Image")
        edited1_radio = QRadioButton("Edited Image 1")
        edited2_radio = QRadioButton("Edited Image 2")
        
        button_group.addButton(original_radio)
        button_group.addButton(edited1_radio)
        button_group.addButton(edited2_radio)
        
        original_radio.setChecked(True)

        layout.addWidget(original_radio)
        layout.addWidget(edited1_radio)
        layout.addWidget(edited2_radio)

        # Confirm button
        confirm_button = QPushButton("Select")
        confirm_button.clicked.connect(dialog.accept)

        layout.addWidget(confirm_button)
        dialog.setLayout(layout)

        # Show the dialog
        if dialog.exec_() == QDialog.Accepted:
            # Determine which image to use for selection
            if original_radio.isChecked():
                selection_label = self.original_image_label
            elif edited1_radio.isChecked():
                selection_label = self.edited_image_label1
            else:
                selection_label = self.edited_image_label2

            # Deactivate selection on all labels
            self.original_image_label.selection_active = False
            self.edited_image_label1.selection_active = False
            self.edited_image_label2.selection_active = False

            # Activate selection mode on the chosen label
            selection_label.selection_active = True
            selection_label.selected_points = []
            selection_label.selection_rect = None
            
            # Store the current selection label
            self.current_selection_label = selection_label
            
            self.confirm_selection_button.show()
            self.select_area_button.setEnabled(False)
            self.select_reference_button.setEnabled(False)
            self.select_2nd_button.setEnabled(False)

            # Force update to ensure the red selection box is drawn
            selection_label.update()

    def start_2nd_selection(self):
        """Start Second selection mode."""
        # Create a dialog to choose the image for selection
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Image for Second Area")
        layout = QVBoxLayout()

        # Radio buttons for image selection
        button_group = QButtonGroup()
        original_radio = QRadioButton("Original Image")
        edited1_radio = QRadioButton("Edited Image 1")
        edited2_radio = QRadioButton("Edited Image 2")
        
        button_group.addButton(original_radio)
        button_group.addButton(edited1_radio)
        button_group.addButton(edited2_radio)
        
        original_radio.setChecked(True)

        layout.addWidget(original_radio)
        layout.addWidget(edited1_radio)
        layout.addWidget(edited2_radio)

        # Confirm button
        confirm_button = QPushButton("Select")
        confirm_button.clicked.connect(dialog.accept)

        layout.addWidget(confirm_button)
        dialog.setLayout(layout)

        # Show the dialog
        if dialog.exec_() == QDialog.Accepted:
            # Determine which image to use for selection
            if original_radio.isChecked():
                selection_label = self.original_image_label
            elif edited1_radio.isChecked():
                selection_label = self.edited_image_label1
            else:
                selection_label = self.edited_image_label2

            # Deactivate selection on all labels
            self.original_image_label.selection_active = False
            self.edited_image_label1.selection_active = False
            self.edited_image_label2.selection_active = False

            # Activate selection mode on the chosen label
            selection_label.selection_active = True
            selection_label.selected_points = []
            selection_label.selection_rect = None
            
            # Store the current selection label
            self.current_selection_label = selection_label
            
            self.confirm_selection_button.show()
            self.select_area_button.setEnabled(False)
            self.select_reference_button.setEnabled(False)
            self.select_2nd_button.setEnabled(False)

            # Force update to ensure the red selection box is drawn
            selection_label.update()

    def confirm_selection(self):
        """Confirm the current selection."""
        if not hasattr(self, 'current_selection_label'):
            QMessageBox.warning(self, "Warning", "No image selected for selection.")
            return

        selection_label = self.current_selection_label
        if selection_label.selection_rect and isinstance(selection_label.selection_rect, QRect):
            # Determine the source image for scaling
            if selection_label == self.original_image_label:
                source_pixmap = self.original_image_label.pixmap()
                source_array = self.original_pixel_array
            elif selection_label == self.edited_image_label1:
                source_pixmap = self.edited_image_label1.pixmap()
                source_array = self.convert_pixmap_to_numpy(source_pixmap)
            else:
                source_pixmap = self.edited_image_label2.pixmap()
                source_array = self.convert_pixmap_to_numpy(source_pixmap)

            if source_pixmap is None or source_array is None:
                QMessageBox.warning(self, "Warning", "Could not process the selected image.")
                return

            # Get display and actual image dimensions
            display_width = source_pixmap.width()
            display_height = source_pixmap.height()
            actual_height, actual_width = source_array.shape[:2]

            # Calculate scaling factors
            scale_x = actual_width / display_width
            scale_y = actual_height / display_height

            # Convert selection rect to actual image coordinates
            rect = selection_label.selection_rect
            x1 = int(rect.x() * scale_x)
            y1 = int(rect.y() * scale_y)
            width = int(rect.width() * scale_x)
            height = int(rect.height() * scale_y)

            # Ensure coordinates are within bounds
            x1 = max(0, min(x1, actual_width - 1))
            y1 = max(0, min(y1, actual_height - 1))
            x2 = min(x1 + width, actual_width)
            y2 = min(y1 + height, actual_height)

            # Store the selection
            if not self.selected_area:
                self.selected_area = QRect(x1, y1, x2 - x1, y2 - y1)
                print(f"Signal area selected: {self.selected_area}")
            elif not self.selected_reference:
                self.selected_reference = QRect(x1, y1, x2 - x1, y2 - y1)
                print(f"Reference area selected: {self.selected_reference}")
            else:
                self.selected_2nd = QRect(x1, y1, x2 - x1, y2 - y1)
                print(f"Second area selected: {self.selected_2nd}")

        # Reset selection state
        selection_label.selection_active = False
        selection_label.update()
        self.confirm_selection_button.hide()
        self.select_area_button.setEnabled(True)
        self.select_reference_button.setEnabled(True)
        self.select_2nd_button.setEnabled(True)

        # Remove the current selection label
        if hasattr(self, 'current_selection_label'):
            del self.current_selection_label

        # Print selection status
        print(f"Signal area: {self.selected_area is not None}")
        print(f"Reference area: {self.selected_reference is not None}")
        print(f"Second area: {self.selected_2nd is not None}")

    def show_SNR(self):

        """Calculate and display SNR results without showing images."""
        if not (self.selected_area and self.selected_reference):
            self.snr_display.setText("Please select both signal area and reference area first.")
            return

        results = self.calculate_snr()
        if results is None:
            self.snr_display.setText("Error calculating SNR. Please check selections.")
            return

        result_text = f"""
Signal-to-Noise Ratio (SNR): {results['snr']:.2f}

Detailed Measurements:
• Signal Region:
  - Mean: {results['signal_mean']:.2f}
  - Std Dev: {results['signal_std']:.2f}
• Noise Region:
  - Mean: {results['noise_mean']:.2f}
  - Std Dev: {results['noise_std']:.2f}
"""
        self.snr_display.setText(result_text)

        # Initialize state
        self.image = None
        self.original_image = None
        self.current_image = None
        self.zoom_factor = 1.0
        self.selected_area = None
        self.selected_reference = None
        self.selected_2nd = None     

    def show_CNR(self):
        """Calculate and display CNR results without showing images."""
        if not (self.selected_area and self.selected_reference and self.selected_2nd):
            self.cnr_display.setText("Please select signal area, reference area and second area first.")
            return

        results = self.calculate_cnr()
        if results is None:
            self.cnr_display.setText("Error calculating CNR. Please check selections.")
            return

        result_text = f"""
Contrast-to-Noise Ratio (CNR): {results['cnr']:.2f}

Detailed Measurements:
• Signal Region:
  - Mean: {results['signal_mean']:.2f}
  - Std Dev: {results['signal_std']:.2f}
• Reference Region:
  - Mean: {results['reference_mean']:.2f}
  - Std Dev: {results['reference_std']:.2f}
• Second Region:
  - Mean: {results['second_mean']:.2f}
  - Std Dev: {results['second_std']:.2f}
"""
        self.cnr_display.setText(result_text)

        # Initialize state
        self.image = None
        self.original_image = None
        self.current_image = None
        self.zoom_factor = 1.0
        self.selected_area = None
        self.selected_reference = None
        self.selected_2nd = None

    def load_image(self):
        """Load a DICOM image and display it."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Open DICOM File", "", "DICOM Files (*.dcm)")
        if not file_path:
            return

        try:
            print(f"Loading DICOM file: {file_path}")
            self.dicom_data = pydicom.dcmread(file_path)
            self.original_pixel_array = self.dicom_data.pixel_array
            
            print(f"Original pixel array shape: {self.original_pixel_array.shape}")
            print(f"Original pixel array type: {self.original_pixel_array.dtype}")

            if hasattr(self.dicom_data, "WindowWidth") and hasattr(self.dicom_data, "WindowCenter"):
                self.original_pixel_array = apply_windowing(self.original_pixel_array, self.dicom_data)

            # Ensure the image is in uint8 format
            if self.original_pixel_array.dtype != np.uint8:
                self.original_pixel_array = self.normalize_to_uint8(self.original_pixel_array)

            self.show_image(self.original_image_label, self.original_pixel_array)
            
            # Clear edited images
            self.edited_image_label1.clear()
            self.edited_image_label2.clear()
            
            # Update calculator with image parameters
            self.pixels_input.setValue(self.original_pixel_array.shape[0])
            if hasattr(self.dicom_data, "PixelSpacing"):
                self.resolution_input.setValue(self.dicom_data.PixelSpacing[0])
                self.auto_calculate()

            self.processing_history.clear()
            self.selected_area = None
            self.selected_reference = None

            print("Image loaded successfully")

        except Exception as e:
            print(f"Failed to load DICOM file: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load DICOM file: {e}")

    def show_image(self, label, pixel_array):
        """Display a numpy array as an image in a QLabel."""
        if pixel_array is None:
            return

        height, width = pixel_array.shape[:2]

        # Handle grayscale and RGB images
        if len(pixel_array.shape) == 2:
            # Grayscale image
            qimage = QImage(pixel_array.data, width, height, width, QImage.Format_Grayscale8)
        elif len(pixel_array.shape) == 3 and pixel_array.shape[2] == 3:
            # RGB image
            qimage = QImage(pixel_array.data, width, height, 3 * width, QImage.Format_RGB888)
            qimage = qimage.rgbSwapped()
        else:
            QMessageBox.warning(self, "Warning", "Unsupported image format.")
            return

        pixmap = QPixmap.fromImage(qimage)

        # Scale the pixmap to fit the label's size while maintaining the aspect ratio
        pixmap = pixmap.scaled(label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)

        label.setPixmap(pixmap)
        label.setAlignment(Qt.AlignCenter)

    def load_standard_image(self):
        """Load a standard image file and display it."""
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Image File", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff);;All Files (*)",
            options=options
        )
        if not file_path:
            return

        try:
            image = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
            if image is None:
                raise Exception("Failed to load image.")

            # Handle grayscale and color images
            if len(image.shape) == 2:
                # Grayscale image
                pass
            elif len(image.shape) == 3 and image.shape[2] == 3:
                # Color image, convert from BGR to RGB
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)  # Correcting the color conversion
            else:
                raise Exception("Unsupported image format.")
            self.original_pixel_array = image
            self.show_image(self.original_image_label, self.original_pixel_array)

            # Clear edited images
            self.edited_image_label1.clear()
            self.edited_image_label2.clear()

            # Update calculator with image parameters
            self.pixels_input.setValue(self.original_pixel_array.shape[0])

            self.processing_history.clear()
            self.selected_area = None
            self.selected_reference = None

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load image: {e}")

    def calculate_snr(self):
        """Calculate Signal-to-Noise Ratio."""
        if not (self.selected_area and self.selected_reference):
            return None

        try:
            # Get signal statistics
            signal_stats = self.get_region_stats(self.selected_area)
            if signal_stats is None:
                return None
            signal_mean, signal_std = signal_stats

            # Get background (noise) statistics
            noise_stats = self.get_region_stats(self.selected_reference)
            if noise_stats is None:
                return None
            noise_mean, noise_std = noise_stats

            # Calculate SNR using the standard formula:
            # SNR = (Signal Mean - Background Mean) / Background Standard Deviation
            snr = abs(signal_mean - noise_mean) / noise_std if noise_std != 0 else 0

            return {
                'snr': snr,
                'signal_mean': signal_mean,
                'signal_std': signal_std,
                'noise_mean': noise_mean,
                'noise_std': noise_std
            }

        except Exception as e:
            print(f"Error calculating SNR: {e}")
            return None

    def calculate_cnr(self):
        """Calculate Contrast-to-Noise Ratio."""
        if not (self.selected_area and self.selected_reference and self.selected_2nd):
            return None

        try:
            # Get signal statistics
            signal_stats = self.get_region_stats(self.selected_area)
            if signal_stats is None:
                return None
            signal_mean, signal_std = signal_stats

            # Get second area statistics
            second_stats = self.get_region_stats(self.selected_2nd)
            if second_stats is None:
                return None
            second_mean, second_std = second_stats

            # Get background (reference) statistics
            reference_stats = self.get_region_stats(self.selected_reference)
            if reference_stats is None:
                return None
            reference_mean, reference_std = reference_stats

            # Calculate CNR using the modified formula:
            # CNR = (Signal Mean - Second Mean) / Reference Mean
            cnr = (signal_mean - second_mean) / reference_mean if reference_mean != 0 else 0

            return {
                'cnr': cnr,
                'signal_mean': signal_mean,
                'signal_std': signal_std,
                'second_mean': second_mean,
                'second_std': second_std,
                'reference_mean': reference_mean,
                'reference_std': reference_std
            }

        except Exception as e:
            print(f"Error calculating CNR: {e}")
            return None

    def get_region_stats(self, rect):
        """Calculate statistics for a selected region."""
        try:
            # Determine the source image and array
            if self.original_pixel_array is None:
                print("No image loaded")
                return None

            # Determine which image to use based on the rect's source
            if rect.x() < self.original_image_label.width():
                # Selection from original image
                img_array = self.original_pixel_array
                source_pixmap = self.original_image_label.pixmap()
            elif rect.x() < (self.original_image_label.width() + self.edited_image_label1.width()):
                # Selection from edited image 1
                pixmap = self.edited_image_label1.pixmap()
                img_array = self.convert_pixmap_to_numpy(pixmap)
                source_pixmap = self.edited_image_label1.pixmap()
            else:
                # Selection from edited image 2
                pixmap = self.edited_image_label2.pixmap()
                img_array = self.convert_pixmap_to_numpy(pixmap)
                source_pixmap = self.edited_image_label2.pixmap()

            if img_array is None or source_pixmap is None:
                print("No image array available")
                return None

            # Get the current displayed image size
            display_width = source_pixmap.width()
            display_height = source_pixmap.height()

            # Get original image dimensions
            img_height, img_width = img_array.shape[:2]

            # Calculate scaling factors
            scale_x = img_width / display_width
            scale_y = img_height / display_height

            # Convert QRect coordinates to image coordinates
            x1 = int(rect.x() * scale_x)
            y1 = int(rect.y() * scale_y)
            width = int(rect.width() * scale_x)
            height = int(rect.height() * scale_y)
            
            # Calculate x2 and y2
            x2 = x1 + width
            y2 = y1 + height
            
            # Ensure coordinates are within bounds
            x1 = max(0, min(x1, img_width - 1))
            y1 = max(0, min(y1, img_height - 1))
            x2 = max(0, min(x2, img_width - 1))
            y2 = max(0, min(y2, img_height - 1))

            # Extract the region from the image array
            region = img_array[y1:y2, x1:x2]

            # Calculate statistics
            mean = np.mean(region)
            std = np.std(region)

            # Return the calculated statistics
            return mean, std

        except Exception as e:
            print(f"Error processing the region: {e}")
            return None

    def reset_view(self):
        self.zoom_slider.setValue(1000)  # Reset slider to represent 100% zoom
        self.zoom_factor = 1.0
        self.current_image = self.original_pixel_array.copy()
        self.show_image(self.original_image_label, self.current_image)
        self.edited_image_label1.clear()
        self.edited_image_label2.clear()
        self.snr_display.clear()
        self.selected_area = None
        self.selected_reference = None
        self.selected_2nd = None
        self.processing_history.clear()

    def clear_results(self):
        """Clear the results displayed in the SNR display and reset selections."""
        self.snr_display.clear()
        self.cnr_display.clear()
        self.selected_area = None
        self.selected_reference = None
        self.selected_2nd = None

        # Optionally, reset the contrast toggle
        self.contrast_toggle = 0
        print("Results cleared.")

    def normalize_image(self, image): 
        min_val = image.min() 
        max_val = image.max() 
        if max_val > min_val: 
            return (image - min_val) / (max_val - min_val) 
        return np.zeros_like(image, dtype=np.float32) 

if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = DicomImageEditor()
    editor.show()
    sys.exit(app.exec_())
