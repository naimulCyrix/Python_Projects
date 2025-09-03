import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QGroupBox, QColorDialog, QFileDialog, QSpinBox,
                             QMessageBox, QFrame, QComboBox, QCheckBox)
from PyQt5.QtGui import QPixmap, QColor, QFont, QImage
from PyQt5.QtCore import Qt
import qrcode
from PIL import Image, ImageDraw
from datetime import datetime


class QRCodeGenerator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.default_save_dir = os.path.expanduser("~/Documents/QR Codes")
        self.initUI()

    def initUI(self):
        self.setWindowTitle('QR Code Studio Pro')
        self.setGeometry(100, 100, 1000, 750)
        self.setMinimumSize(900, 650)

        # Set application style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f7;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #2c3e50;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
            QLineEdit {
                padding: 8px;
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #3498db;
            }
            QLabel {
                color: #2c3e50;
            }
            QSpinBox {
                padding: 6px;
                border: 2px solid #bdc3c7;
                border-radius: 6px;
            }
            QComboBox {
                padding: 6px;
                border: 2px solid #bdc3c7;
                border-radius: 6px;
            }
            QCheckBox {
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
            }
        """)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QHBoxLayout(central_widget)

        # Left panel for controls
        left_panel = QFrame()
        left_panel.setMaximumWidth(400)
        left_panel.setFrameStyle(QFrame.StyledPanel)
        left_panel.setStyleSheet("background-color: white; border-radius: 10px;")
        left_layout = QVBoxLayout(left_panel)

        # App title
        title = QLabel("QR Code Studio Pro")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setStyleSheet("color: #2c3e50; padding: 10px;")
        title.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(title)

        # Input section
        input_group = QGroupBox("Content to Encode")
        input_layout = QVBoxLayout()

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Enter text, URL, or other content here...")
        input_layout.addWidget(self.input_field)

        input_group.setLayout(input_layout)
        left_layout.addWidget(input_group)

        # Customization section
        custom_group = QGroupBox("Customization Options")
        custom_layout = QVBoxLayout()

        # Color selection
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("QR Color:"))
        self.color_btn = QPushButton()
        self.color_btn.clicked.connect(self.choose_color)
        self.color_btn.setStyleSheet("background-color: #e74c3c; border-radius: 4px; min-width: 30px;")
        self.qr_color = (231, 76, 60)  # Default red as RGB tuple

        color_layout.addWidget(self.color_btn)
        color_layout.addStretch()

        color_layout.addWidget(QLabel("Background:"))
        self.bg_color_btn = QPushButton()
        self.bg_color_btn.clicked.connect(self.choose_bg_color)
        self.bg_color_btn.setStyleSheet("background-color: #ffffff; border-radius: 4px; min-width: 30px;")
        self.bg_color = (255, 255, 255)  # Default white as RGB tuple

        color_layout.addWidget(self.bg_color_btn)
        custom_layout.addLayout(color_layout)

        # Size selection
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Size:"))
        self.size_spinner = QSpinBox()
        self.size_spinner.setRange(100, 1000)
        self.size_spinner.setValue(300)
        self.size_spinner.setSuffix(" px")
        size_layout.addWidget(self.size_spinner)
        custom_layout.addLayout(size_layout)

        # Error correction level
        error_layout = QHBoxLayout()
        error_layout.addWidget(QLabel("Error Correction:"))
        self.error_combo = QComboBox()
        self.error_combo.addItems(["Low (7%)", "Medium (15%)", "Quartile (25%)", "High (30%)"])
        self.error_combo.setCurrentIndex(1)  # Medium by default
        error_layout.addWidget(self.error_combo)
        custom_layout.addLayout(error_layout)

        # QR code style
        style_layout = QHBoxLayout()
        style_layout.addWidget(QLabel("Style:"))
        self.style_combo = QComboBox()
        self.style_combo.addItems(["Standard", "Rounded", "Dots"])
        style_layout.addWidget(self.style_combo)
        custom_layout.addLayout(style_layout)

        custom_group.setLayout(custom_layout)
        left_layout.addWidget(custom_group)

        # Generate button
        self.generate_btn = QPushButton("Generate QR Code")
        self.generate_btn.clicked.connect(self.generate_qr)
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                font-size: 16px;
                padding: 12px;
            }
            QPushButton:hover {
                background-color: #219653;
            }
        """)
        left_layout.addWidget(self.generate_btn)

        # Save options group
        save_group = QGroupBox("Save Options")
        save_layout = QVBoxLayout()

        # Save directory selection
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("Save Folder:"))
        self.dir_btn = QPushButton("Choose Folder")
        self.dir_btn.clicked.connect(self.choose_save_directory)
        self.dir_btn.setStyleSheet("font-size: 12px; padding: 6px;")
        dir_layout.addWidget(self.dir_btn)
        save_layout.addLayout(dir_layout)

        # Current directory display
        self.dir_label = QLabel(f"Current: {self.default_save_dir}")
        self.dir_label.setStyleSheet("color: #7f8c8d; font-size: 11px; font-style: italic;")
        self.dir_label.setWordWrap(True)
        save_layout.addWidget(self.dir_label)

        # Filename options
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("File Name:"))
        self.filename_edit = QLineEdit()
        self.filename_edit.setPlaceholderText("qrcode")
        self.filename_edit.setEnabled(False)
        name_layout.addWidget(self.filename_edit)
        save_layout.addLayout(name_layout)

        # Auto naming option
        self.auto_name = QCheckBox("Use automatic naming (timestamp)")
        self.auto_name.setChecked(True)
        self.auto_name.stateChanged.connect(self.toggle_filename_edit)
        save_layout.addWidget(self.auto_name)

        # Format selection
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPEG"])
        format_layout.addWidget(self.format_combo)
        save_layout.addLayout(format_layout)

        # Save buttons
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save QR Code")
        self.save_btn.clicked.connect(self.save_qr)
        self.save_btn.setEnabled(False)  # Initially disabled

        self.save_as_btn = QPushButton("Save As...")
        self.save_as_btn.clicked.connect(self.save_qr_as)
        self.save_as_btn.setEnabled(False)  # Initially disabled

        button_layout.addWidget(self.save_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.save_as_btn)
        save_layout.addLayout(button_layout)

        save_group.setLayout(save_layout)
        left_layout.addWidget(save_group)

        left_layout.addStretch()

        # Right panel for QR display
        right_panel = QFrame()
        right_panel.setFrameStyle(QFrame.StyledPanel)
        right_panel.setStyleSheet("background-color: white; border-radius: 10px;")
        right_layout = QVBoxLayout(right_panel)

        # QR code display
        display_label = QLabel("QR Code Preview")
        display_label.setFont(QFont("Arial", 14, QFont.Bold))
        display_label.setAlignment(Qt.AlignCenter)
        display_label.setStyleSheet("padding: 10px; color: #2c3e50;")
        right_layout.addWidget(display_label)

        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setText("Your QR code will appear here")
        self.qr_label.setMinimumSize(350, 350)
        self.qr_label.setStyleSheet("""
            border: 2px dashed #bdc3c7; 
            border-radius: 10px;
            padding: 20px;
            color: #7f8c8d;
            font-style: italic;
        """)
        right_layout.addWidget(self.qr_label)

        # Status bar
        self.status_label = QLabel("Ready to generate QR code")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("padding: 5px; color: #7f8c8d; font-size: 12px;")
        right_layout.addWidget(self.status_label)

        # Add panels to main layout
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)

        # Store the current QR code
        self.current_qr = None
        self.current_save_dir = self.default_save_dir

        # Create default save directory if it doesn't exist
        if not os.path.exists(self.default_save_dir):
            os.makedirs(self.default_save_dir)

    def toggle_filename_edit(self, state):
        self.filename_edit.setEnabled(not state)

    def choose_save_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Save Directory",
                                                     self.current_save_dir)
        if directory:
            self.current_save_dir = directory
            self.dir_label.setText(f"Current: {directory}")

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            # Convert QColor to RGB tuple for qrcode library
            self.qr_color = (color.red(), color.green(), color.blue())
            self.color_btn.setStyleSheet(f"background-color: {color.name()}; border-radius: 4px; min-width: 30px;")

    def choose_bg_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            # Convert QColor to RGB tuple for qrcode library
            self.bg_color = (color.red(), color.green(), color.blue())
            self.bg_color_btn.setStyleSheet(f"background-color: {color.name()}; border-radius: 4px; min-width: 30px;")

    def generate_qr(self):
        text = self.input_field.text().strip()
        if not text:
            QMessageBox.warning(self, "Input Error", "Please enter some text or URL to generate QR code.")
            return

        try:
            # Get error correction level
            error_levels = [
                qrcode.constants.ERROR_CORRECT_L,  # Low
                qrcode.constants.ERROR_CORRECT_M,  # Medium
                qrcode.constants.ERROR_CORRECT_Q,  # Quartile
                qrcode.constants.ERROR_CORRECT_H  # High
            ]
            error_correction = error_levels[self.error_combo.currentIndex()]

            # Create QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=error_correction,
                box_size=10,
                border=4,
            )
            qr.add_data(text)
            qr.make(fit=True)

            # Create image with custom colors
            img = qr.make_image(
                fill_color=self.qr_color,
                back_color=self.bg_color
            ).convert('RGB')

            # Apply style if selected
            style = self.style_combo.currentText()
            if style == "Rounded":
                img = self.apply_rounded_style(img)
            elif style == "Dots":
                img = self.apply_dots_style(img)

            # Resize image
            size = self.size_spinner.value()
            img = img.resize((size, size), Image.LANCZOS)

            # Convert to QPixmap and display
            self.current_qr = img

            # Convert PIL Image to QPixmap
            data = img.tobytes("raw", "RGB")
            qim = QImage(data, img.size[0], img.size[1], QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qim)

            self.qr_label.setPixmap(pixmap)
            self.qr_label.setText("")  # Clear the text

            # Enable save buttons
            self.save_btn.setEnabled(True)
            self.save_as_btn.setEnabled(True)

            # Update status
            self.status_label.setText("QR code generated successfully. Ready to save.")

        except Exception as e:
            QMessageBox.critical(self, "Generation Error", f"An error occurred while generating QR code: {str(e)}")
            self.status_label.setText("Error generating QR code.")

    def apply_rounded_style(self, img):
        """Apply rounded corners to QR code modules"""
        width, height = img.size
        pixels = img.load()

        # Create a new image with the same size
        new_img = Image.new('RGB', (width, height), self.bg_color)
        draw = ImageDraw.Draw(new_img)

        # Draw rounded rectangles for each module
        module_size = max(1, width // 21)  # Estimate module size based on QR version

        for y in range(0, height, module_size):
            for x in range(0, width, module_size):
                # Check if this is a QR code module
                if x < width and y < height and pixels[x, y] == (0, 0, 0):
                    # Draw a rounded rectangle
                    draw.rounded_rectangle(
                        [x, y, x + module_size - 1, y + module_size - 1],
                        radius=module_size // 3,
                        fill=self.qr_color
                    )

        return new_img

    def apply_dots_style(self, img):
        """Convert QR code modules to dots"""
        width, height = img.size
        new_img = Image.new('RGB', (width, height), self.bg_color)
        draw = ImageDraw.Draw(new_img)

        pixels = img.load()

        # Draw circles instead of squares
        module_size = max(3, width // 30)  # Determine dot size based on image size

        for y in range(0, height, module_size):
            for x in range(0, width, module_size):
                # Check if this position should have a dot
                if x < width and y < height and pixels[x, y] == (0, 0, 0):
                    # Draw a circle
                    center_x = x + module_size // 2
                    center_y = y + module_size // 2
                    radius = module_size // 2 - 1
                    draw.ellipse(
                        [center_x - radius, center_y - radius,
                         center_x + radius, center_y + radius],
                        fill=self.qr_color
                    )

        return new_img

    def generate_filename(self):
        """Generate a filename based on user preferences"""
        if self.auto_name.isChecked():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"qrcode_{timestamp}"
        else:
            filename = self.filename_edit.text().strip()
            return filename if filename else "qrcode"

    def save_qr(self):
        """Save QR code to the selected directory"""
        if not self.current_qr:
            return

        try:
            # Generate filename
            base_filename = self.generate_filename()
            format_name = self.format_combo.currentText()
            file_ext = format_name.lower()

            # Create full path
            file_path = os.path.join(self.current_save_dir, f"{base_filename}.{file_ext}")

            # Handle file name conflicts
            counter = 1
            while os.path.exists(file_path):
                file_path = os.path.join(self.current_save_dir, f"{base_filename}_{counter}.{file_ext}")
                counter += 1

            # Save the image
            if format_name == "JPEG":
                self.current_qr.convert('RGB').save(file_path, "JPEG", quality=95)
            else:
                self.current_qr.save(file_path, "PNG")

            # Update status
            self.status_label.setText(f"QR code saved to: {os.path.basename(file_path)}")

            # Show success message
            QMessageBox.information(self, "Success", f"QR code saved successfully to:\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"An error occurred while saving: {str(e)}")
            self.status_label.setText("Error saving QR code.")

    def save_qr_as(self):
        """Save QR code with custom location dialog"""
        if not self.current_qr:
            return

        format_name = self.format_combo.currentText()
        file_ext = format_name.lower()

        # Generate suggested filename
        base_filename = self.generate_filename()

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save QR Code As",
            os.path.join(self.current_save_dir, f"{base_filename}.{file_ext}"),
            f"{format_name} Files (*.{file_ext});;All Files (*)"
        )

        if file_path:
            try:
                if format_name == "JPEG":
                    self.current_qr.convert('RGB').save(file_path, "JPEG", quality=95)
                else:
                    self.current_qr.save(file_path, "PNG")

                # Update status
                self.status_label.setText(f"QR code saved to: {os.path.basename(file_path)}")

                QMessageBox.information(self, "Success", f"QR code saved successfully as {os.path.basename(file_path)}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"An error occurred while saving: {str(e)}")
                self.status_label.setText("Error saving QR code.")


def main():
    app = QApplication(sys.argv)

    # Set application font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    generator = QRCodeGenerator()
    generator.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()