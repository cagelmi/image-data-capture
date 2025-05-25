# Python Image Data Digitizer

A Python-based tool with a graphical user interface (GUI) designed to extract numerical data points (X, Y coordinates) from plot or graph images when the original dataset is unavailable.

## Inspiration and Development

This project is inspired by the functionality of the excellent `digitize2.m` MATLAB script available on the MathWorks File Exchange, created by Anil Prasad.

**Citation for original MATLAB script:**
> Anil (2025). digitize2.m (https://www.mathworks.com/matlabcentral/fileexchange/928-digitize2-m), MATLAB Central File Exchange. Retrieved May 2, 2025.

The initial translation from MATLAB to Python and subsequent refinements for this project were developed with the assistance of Google's Gemini 2.5 Pro Preview model.

## Features

*   Loads standard image formats (JPEG, PNG, TIFF, BMP, GIF).
*   Interactive GUI based on Matplotlib and Tkinter.
*   User defines the coordinate system by clicking:
    *   Origin point
    *   A known point on the X-axis
    *   A known point on the Y-axis
*   Prompts for the corresponding data values at the clicked reference points.
*   Supports both **Linear** and **Logarithmic** scales independently for the X and Y axes.
*   Clear **GUI instructions** overlaid on the plot guide the user through each step.
*   Acquire data points by simply **left-clicking** on the plot.
*   Finish data acquisition with a **right-click** or **middle-click**.
*   Calculates and displays the extracted (X, Y) data coordinates in the console.
*   Saves the extracted data to:
    *   A **Text file (`.txt`)** including a header with metadata (image name, axis definitions).
    *   An **Excel file (`.xlsx`)** containing just the X and Y data columns.

## Screenshot

Here's a visual demonstration of the tool in action:

**1. Initial Plot Image Loaded:**
The user starts by loading the target image file into the digitizer window.

![Initial plot image before digitization](https://raw.githubusercontent.com/cagelmi/image-data-capture/main/images/fig1.png)

---

**2. Axis & Data Points Selected:**
After defining the origin (green marker), X-axis point (blue marker), Y-axis point (red marker), and clicking on several data points (small red dots), the image might look like this just before finishing the acquisition and saving the extracted data. The GUI prompts (red text overlay) guide the user through each step.

<img src="https://raw.githubusercontent.com/cagelmi/image-data-capture/main/images/fig1_data_captured.png" alt="Plot image after selecting axis points and data points" width="700"/>

## Requirements

*   Python 3.x
*   Libraries:
    *   `matplotlib`
    *   `numpy`
    *   `Pillow` (PIL Fork)
    *   `pandas`
    *   `openpyxl` (for writing `.xlsx` files with pandas)

## Installation

1.  **Ensure Python 3 is installed.** You can download it from [python.org](https://www.python.org/).
2.  **Clone or download this repository.**
3.  **(Recommended) Create and activate a virtual environment:**
    *   Using standard Python `venv`:
        ```bash
        python -m venv venv
        source venv/bin/activate  # On Linux/macOS
        venv\Scripts\activate.bat   # On Windows CMD
        venv\Scripts\Activate.ps1 # On Windows PowerShell
        ```
    *   Using Conda:
        ```bash
        conda create --name image_digitizer_env python=3.9 # Or your preferred version
        conda activate image_digitizer_env
        ```
4.  **Install the required libraries:** Navigate to the project directory in your terminal (with the virtual environment activated) and run:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  **Run the script** from your terminal:
    ```bash
    python image_digitizer.py
    ```
2.  A **file dialog** will appear. Select the image file containing the plot you want to digitize.
3.  The image will be displayed in a Matplotlib window.
4.  **Follow the red instruction text** displayed at the top of the plot window:
    *   **Step 1: Click the Origin.** Click the point on the plot that corresponds to the origin (e.g., where X=0 and Y=0, or your defined minimums).
    *   A dialog box will appear. **Enter the actual X and Y data values** for the origin point you clicked.
    *   **Step 2: Click X-Axis Point.** Click another known point *along the X-axis* (it doesn't have to be the maximum, just a known point different from the origin).
    *   A dialog box will appear. **Enter the actual X data value** for this point.
    *   A dialog box will ask if the **X-axis is Linear or Logarithmic**. Choose accordingly.
    *   **Step 3: Click Y-Axis Point.** Click another known point *along the Y-axis* (different from the origin).
    *   A dialog box will appear. **Enter the actual Y data value** for this point.
    *   A dialog box will ask if the **Y-axis is Linear or Logarithmic**. Choose accordingly.
5.  **Step 4: Acquire Data Points:** The instruction text will update.
    *   **Left-click** directly on the data points on the plot curve/scatter that you want to extract. A small red marker will appear, and the calculated (X, Y) coordinates will be printed in the terminal.
    *   Continue left-clicking all desired points.
6.  **Finish Acquisition:** When you have clicked all desired data points, **right-click** or **middle-click** anywhere on the plot window.
7.  A **save file dialog** will appear. Choose a location and filename for the output data. The script will automatically save *both* a `.txt` and an `.xlsx` file using the base name you provide.
8.  The Matplotlib window will close, and the script will terminate.

## Output Files

For a chosen save name like `my_extracted_data`, the script generates:

1.  **`my_extracted_data.txt`**:
    *   Contains a header section (`#` comments) with metadata: image filename, timestamp, axis definitions (pixel coordinates, data values, scale type).
    *   Below the header, contains two columns of data: `X_Data` and `Y_Data`.
2.  **`my_extracted_data.xlsx`**:
    *   An Excel spreadsheet with two columns: `X_Data` and `Y_Data`.
    *   Contains only the numerical data, no header metadata.

## License

This project is licensed under the **GNU General Public License v3.0**.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

This means you are free to run, study, share, and modify the software. However, if you distribute modified versions or works based on this software, you must do so under the same GPLv3 license terms, ensuring the source code remains available.

Please see the `LICENSE` file included in this repository for the full text of the license.

## Contributing

Contributions, issues, and feature requests are welcome. Please feel free to open an issue or submit a pull request.
