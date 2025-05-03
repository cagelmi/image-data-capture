#!/usr/bin/env python3
"""
Digitize Data from Image Plots.

This script allows a user to load an image containing a plot, define the
coordinate system (origin, X/Y axes, linear/log scale) by clicking points
and entering values, and then click on data points within the plot to extract
their corresponding X, Y data coordinates.

The extracted data is saved to both a text file (with metadata header) and
an Excel file (.xlsx).
"""

# --- Standard Library Imports ---
import os
import math
import traceback  # For detailed error reporting
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox

# --- Third-Party Imports ---
# Ensure these are installed: pip install matplotlib numpy Pillow pandas openpyxl
import matplotlib
matplotlib.use('TkAgg')  # Use the Tkinter backend for compatibility (MUST be before pyplot import)
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import pandas as pd
import openpyxl # Engine for pandas to write .xlsx files

print("INFO: Libraries imported and Matplotlib backend set to TkAgg.")

# --- Constants ---
MATRIX_SINGULARITY_THRESHOLD = 1e-6 # Tolerance for checking collinear axis points
ZERO_DIVISION_THRESHOLD = 1e-9     # Tolerance for checking near-zero scale differences

# --- Global variables ---
# Used to share state between main function and GUI callbacks/helpers
fig = None
ax = None
instruction_text_obj = None # To hold the reference to the instruction text on the plot
print("INFO: Global fig, ax, instruction_text_obj initialized to None.")


# --- Helper Functions ---

def show_instruction(text_to_show):
    """
    Displays or clears instruction text overlay on the Matplotlib figure.

    Args:
        text_to_show (str): The instruction text to display. If empty or None,
                            clears any existing instruction.
    """
    global instruction_text_obj, fig
    if fig is None or not plt.fignum_exists(fig.number):
        # Figure doesn't exist or was closed, nothing to do
        return

    # --- Remove previous instruction ---
    if instruction_text_obj:
        try:
            # Check if the object is still attached to a figure before removing
            if instruction_text_obj.figure is not None:
                 instruction_text_obj.remove()
        except Exception:
             pass # Ignore if already gone
        instruction_text_obj = None # Reset reference

    # --- Add new instruction text ---
    if text_to_show:
        try:
            instruction_text_obj = fig.text(
                0.5, 0.97, # Position: top-center
                text_to_show,
                ha='center', va='top', # Alignment
                fontsize=14, fontweight='bold', color='red',
                # Background box for better visibility
                bbox={'facecolor': 'wheat', 'alpha': 0.85, 'pad': 5}
            )
        except Exception as e:
            print(f"Warning: Could not display instruction text: {e}")
            instruction_text_obj = None # Ensure reset on error

    # --- Redraw canvas ---
    try:
        # Use draw_idle for efficiency - schedules a redraw if needed
        fig.canvas.draw_idle()
    except Exception:
        pass # Ignore draw errors if window is closing etc.

def _create_dialog_root():
    """Creates and prepares a hidden Tk root for dialogs."""
    root = tk.Tk()
    root.withdraw() # Hide the main window
    root.update()   # Process events, necessary before showing dialog
    return root

def get_user_input(prompt, title, initialvalue=""):
    """Gets string input from the user via a simple Tkinter dialog."""
    root = _create_dialog_root()
    user_input = tk.simpledialog.askstring(title, prompt, initialvalue=initialvalue, parent=root)
    root.update()
    root.destroy()
    return user_input

def get_float_input(prompt, title, initialvalue=0.0):
    """
    Gets float input from the user, handling errors and clearing plot instructions.
    """
    show_instruction("") # Clear plot instruction before showing dialog
    while True:
        value_str = get_user_input(prompt, title, initialvalue=str(initialvalue))
        if value_str is None:
            print("INFO: User cancelled float input.")
            return None # User cancelled dialog
        try:
            return float(value_str)
        except ValueError:
            print("ERROR: Invalid float input entered.")
            root_msg = _create_dialog_root()
            tk.messagebox.showerror("Invalid Input", f"Please enter a valid number for '{title}'.", parent=root_msg)
            root_msg.update()
            root_msg.destroy()
            # Loop continues to ask again

def get_axis_type(axis_name):
    """Asks user if an axis is linear or logarithmic via a Tkinter dialog."""
    show_instruction("") # Clear plot instruction before showing dialog
    root = _create_dialog_root()
    is_log_str = tk.messagebox.askquestion(
        "Axis Type",
        f"Is the {axis_name}-axis LOGARITHMIC?\n(Select 'No' for Linear)",
        icon='question',
        parent=root
    )
    # askquestion returns 'yes' or 'no' string
    is_log = (is_log_str == 'yes')
    print(f"INFO: {axis_name}-axis type selected: {'Logarithmic' if is_log else 'Linear'}")
    root.update()
    root.destroy()
    return is_log

def transform_coords(px, py, origin_px, xaxis_px, yaxis_px,
                     origin_data, xaxis_data, yaxis_data,
                     is_log_x, is_log_y):
    """
    Transforms pixel coordinates (px, py) to data coordinates based on
    the defined axes and scales.

    Args:
        px, py (float): Pixel coordinates of the point to transform.
        origin_px (tuple): Pixel coordinates (x, y) of the origin.
        xaxis_px (tuple): Pixel coordinates (x, y) of the X-axis reference point.
        yaxis_px (tuple): Pixel coordinates (x, y) of the Y-axis reference point.
        origin_data (tuple): Data coordinates (x, y) of the origin.
        xaxis_data (float): Data X-coordinate of the X-axis reference point.
        yaxis_data (float): Data Y-coordinate of the Y-axis reference point.
        is_log_x (bool): True if the X-axis is logarithmic.
        is_log_y (bool): True if the Y-axis is logarithmic.

    Returns:
        tuple: (data_x, data_y) coordinates, or (np.nan, np.nan) on error.
    """
    # --- Calculate transformation matrix from pixel vectors ---
    vec_origin_to_p = np.array([px - origin_px[0], py - origin_px[1]])
    vec_origin_to_x = np.array([xaxis_px[0] - origin_px[0], xaxis_px[1] - origin_px[1]])
    vec_origin_to_y = np.array([yaxis_px[0] - origin_px[0], yaxis_px[1] - origin_px[1]])

    # Matrix A maps basis coefficients [cx, cy] to pixel vector:
    # A @ [cx, cy]^T = vec_origin_to_p
    pixel_basis_matrix = np.vstack((vec_origin_to_x, vec_origin_to_y)).T

    # --- Check for singularity (collinear axes) ---
    try:
        if abs(np.linalg.det(pixel_basis_matrix)) < MATRIX_SINGULARITY_THRESHOLD:
            print("Warning: Axis points are collinear or too close. Transformation is ill-defined.")
            return (np.nan, np.nan)
        inv_pixel_basis_matrix = np.linalg.inv(pixel_basis_matrix)
    except np.linalg.LinAlgError:
        print("Error: Could not invert pixel transformation matrix (collinear points?).")
        return (np.nan, np.nan)

    # --- Calculate fractional coordinates in pixel basis ---
    # Coeffs [cx, cy] represent how far along each axis vector the point lies
    coeffs = inv_pixel_basis_matrix @ vec_origin_to_p
    cx, cy = coeffs[0], coeffs[1]

    # --- Map fractional coordinates to data coordinates ---
    origin_x_data, origin_y_data = origin_data
    data_x, data_y = np.nan, np.nan # Initialize results

    # Calculate X Data Coordinate
    if is_log_x:
        if origin_x_data <= 0 or xaxis_data <= 0:
            print("Warning: Log X-axis requires positive origin and reference point data values.")
        else:
            try:
                log_origin_x = math.log10(origin_x_data)
                log_xaxis_x = math.log10(xaxis_data)
                delta_log_x = log_xaxis_x - log_origin_x
                if abs(delta_log_x) < ZERO_DIVISION_THRESHOLD:
                    data_x = origin_x_data # Avoid issues if points identical in log space
                    print("Warning: X-axis data points too close for reliable log scale interpolation.")
                else:
                    log_data_x = log_origin_x + cx * delta_log_x
                    data_x = 10**log_data_x
            except ValueError as e: # Should not happen with checks, but belt-and-braces
                print(f"Error calculating log X value: {e}")
    else: # Linear X-axis
        delta_x = xaxis_data - origin_x_data
        if abs(delta_x) < ZERO_DIVISION_THRESHOLD:
            data_x = origin_x_data # Avoid issues if points identical
            print("Warning: X-axis data points are identical.")
        else:
            data_x = origin_x_data + cx * delta_x

    # Calculate Y Data Coordinate
    if is_log_y:
        if origin_y_data <= 0 or yaxis_data <= 0:
            print("Warning: Log Y-axis requires positive origin and reference point data values.")
        else:
             try:
                log_origin_y = math.log10(origin_y_data)
                log_yaxis_y = math.log10(yaxis_data)
                delta_log_y = log_yaxis_y - log_origin_y
                if abs(delta_log_y) < ZERO_DIVISION_THRESHOLD:
                    data_y = origin_y_data
                    print("Warning: Y-axis data points too close for reliable log scale interpolation.")
                else:
                    log_data_y = log_origin_y + cy * delta_log_y
                    data_y = 10**log_data_y
             except ValueError as e:
                print(f"Error calculating log Y value: {e}")
    else: # Linear Y-axis
        delta_y = yaxis_data - origin_y_data
        if abs(delta_y) < ZERO_DIVISION_THRESHOLD:
            data_y = origin_y_data
            print("Warning: Y-axis data points are identical.")
        else:
            data_y = origin_y_data + cy * delta_y

    return (data_x, data_y)

print("INFO: Helper functions defined.")


# --- Main Digitization Function ---

def digitize_image():
    """Main function to perform image digitization."""
    global fig, ax, instruction_text_obj # Declare intent to modify globals
    instruction_text_obj = None # Ensure it's reset at start of function call
    print("INFO: digitize_image() started.")

    # --- 1. Select Image File ---
    print("INFO: Prompting user to select image file...")
    root_fd = _create_dialog_root()
    try:
        image_path = tk.filedialog.askopenfilename(
            master=root_fd, # Associate dialog with hidden root
            title="Select Image File",
            filetypes=[
                ("Image Files", "*.jpg *.jpeg *.png *.tif *.tiff *.bmp *.gif"),
                ("All Files", "*.*")
            ]
        )
        print(f"INFO: File dialog returned: {image_path}")
    except Exception as e:
        print(f"ERROR: Exception during file dialog creation: {e}")
        traceback.print_exc()
        image_path = None
    finally:
        # Ensure the root is always destroyed cleanly
        print("INFO: Destroying Tk root for file dialog.")
        root_fd.destroy()

    if not image_path:
        print("INFO: No image file selected or error occurred. Exiting.")
        return

    # --- 2. Load and Display Image ---
    print(f"INFO: Loading image: {image_path}")
    try:
        img = Image.open(image_path)
        # Ensure image is in RGB for consistent display with matplotlib
        if img.mode != 'RGB':
            print(f"INFO: Converting image mode from {img.mode} to RGB.")
            img = img.convert('RGB')
        img_array = np.array(img)
        print(f"INFO: Image loaded successfully. Shape: {img_array.shape}")
    except FileNotFoundError:
        print(f"ERROR: Image file not found at: {image_path}")
        root_err = _create_dialog_root(); tk.messagebox.showerror("Error", f"Image file not found:\n{image_path}", parent=root_err); root_err.destroy()
        return
    except Exception as e:
        print(f"ERROR: Failed to load image: {e}"); traceback.print_exc()
        root_err = _create_dialog_root(); tk.messagebox.showerror("Error", f"Failed to load image:\n{e}", parent=root_err); root_err.destroy()
        return

    print("INFO: Creating Matplotlib figure...")
    try:
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.imshow(img_array)
        ax.set_title(
            f"IMAGE: {os.path.basename(image_path)}\n"
            "(Use GUI prompts / Close window when finished)",
            fontsize=10
        )
        # Hide default axes ticks and labels
        ax.set_xticks([])
        ax.set_yticks([])
        plt.tight_layout() # Adjust layout to prevent overlap
        print("INFO: Figure created. Attempting plt.show(block=False)...")
        plt.show(block=False) # Show plot without blocking script execution
        print("INFO: plt.show(block=False) executed.")
        print("INFO: Attempting fig.canvas.draw_idle()..."); fig.canvas.draw_idle() # Ensure drawing updates
        print("INFO: fig.canvas.draw_idle() executed.")
        fig.canvas.manager.set_window_title("Image Digitizer")
        print("INFO: Image loaded and plot shown. Please follow GUI prompts...")
    except Exception as e:
        print(f"ERROR: Failed during figure creation or display: {e}"); traceback.print_exc()
        # Attempt to close the figure if it was partially created
        if fig and plt.fignum_exists(fig.number): plt.close(fig)
        root_err = _create_dialog_root(); tk.messagebox.showerror("Plot Error", f"Could not display the image plot:\n{e}", parent=root_err); root_err.destroy()
        return

    # --- Nested Helper: get_click_point ---
    # Defined inside to easily access fig, ax without passing them explicitly
    def get_click_point(prompt_message, marker_style='go', marker_size=10):
        """Prompts user via GUI text, gets click, draws marker, returns pixel coords."""
        print(f"\nINFO: Prompting user: {prompt_message}")
        if fig is None or not plt.fignum_exists(fig.number):
            print("ERROR: Figure window seems to be closed before click.")
            return None # Cannot proceed if figure is gone

        fig.canvas.manager.set_window_title(f"Image Digitizer - WAITING FOR CLICK")
        show_instruction(prompt_message) # <<< Show instruction text ON FIGURE

        clicked_points = None
        try:
            print("INFO: Waiting for ginput(1)... (Click on the plot)")
            # ginput blocks until a click occurs or the window is interacted with
            # based on mouse_stop/pop settings. timeout=-1 waits indefinitely.
            clicked_points = plt.ginput(
                n=1,
                timeout=-1,
                show_clicks=True,
                mouse_add=plt.MouseButton.LEFT,
                mouse_stop=plt.MouseButton.RIGHT,
                mouse_pop=plt.MouseButton.MIDDLE
            )
            print(f"INFO: ginput returned: {clicked_points}")
        except Exception as e:
             # This usually happens if the window is closed during the ginput wait
             print(f"ERROR: Error during ginput: {e}")
             if ('destroyed' in str(e).lower()) or ('invalid command name' in str(e).lower()):
                 print("INFO: Window appears to have been closed during ginput.")
             else:
                 print("ERROR: Unexpected error during ginput:"); traceback.print_exc()
             # Fall through to cleanup
        finally:
            # --- Always clear instruction after ginput attempt ---
            show_instruction("")

        if not clicked_points:
            print("INFO: No point selected (likely right/middle click or window closed).")
            return None # User intentionally stopped or window closed

        # Process the successfully clicked point
        px, py = clicked_points[0]
        print(f"INFO: Clicked pixel: ({px:.1f}, {py:.1f})")
        # Plot markers for visual feedback
        ax.plot(px, py, marker_style, markersize=marker_size, markeredgecolor='k')
        ax.plot(px, py, 'kx', markersize=marker_size/1.5) # Add cross inside marker
        fig.canvas.draw_idle() # Update display
        fig.canvas.manager.set_window_title("Image Digitizer"); # Reset title
        return (px, py)

    # --- 3. Define Coordinate System ---
    # Get Origin
    origin_px = get_click_point("1. Click on the plot ORIGIN")
    if origin_px is None: print("INFO: Origin selection failed/cancelled. Exiting."); return
    origin_x_data = get_float_input("Enter X data value at Origin:", "Origin X Value", 0.0)
    if origin_x_data is None: print("INFO: Origin X input cancelled. Exiting."); plt.close(fig); return
    origin_y_data = get_float_input("Enter Y data value at Origin:", "Origin Y Value", 0.0)
    if origin_y_data is None: print("INFO: Origin Y input cancelled. Exiting."); plt.close(fig); return
    origin_data = (origin_x_data, origin_y_data)
    print(f"INFO: Origin defined: px={origin_px}, data={origin_data}")

    # Get X-Axis Reference Point
    xaxis_px = get_click_point("2. Click on a known point on the X-AXIS (not Origin)")
    if xaxis_px is None: print("INFO: X-axis point selection failed/cancelled. Exiting."); plt.close(fig); return
    xaxis_x_data = get_float_input("Enter X data value at this X-Axis point:", "X-Axis Point Value", 1.0)
    if xaxis_x_data is None: print("INFO: X-axis value input cancelled. Exiting."); plt.close(fig); return
    # Validation checks
    if np.allclose(np.array(origin_px), np.array(xaxis_px)):
         print("ERROR: X-axis pixel location cannot be the same as the origin pixel.");
         root_err = _create_dialog_root(); tk.messagebox.showerror("Error", "X-axis point cannot be the same pixel as the origin.", parent=root_err); root_err.destroy(); plt.close(fig); return
    if np.isclose(origin_x_data, xaxis_x_data):
         print("ERROR: X-axis data value cannot be the same as the origin X data value.");
         root_err = _create_dialog_root(); tk.messagebox.showerror("Error", "X-axis data value cannot be the same as the origin X value.", parent=root_err); root_err.destroy(); plt.close(fig); return
    is_log_x = get_axis_type("X")
    if is_log_x and (origin_x_data <= 0 or xaxis_x_data <= 0):
        print("ERROR: Log X-axis requires positive data values > 0.");
        root_err = _create_dialog_root(); tk.messagebox.showerror("Error", "Log scale requires X values > 0 for Origin and X-Axis point.", parent=root_err); root_err.destroy(); plt.close(fig); return
    print(f"INFO: X-axis defined: px={xaxis_px}, data={xaxis_x_data}, log={is_log_x}")

    # Get Y-Axis Reference Point
    yaxis_px = get_click_point("3. Click on a known point on the Y-AXIS (not Origin)", marker_style='rs') # Red square for Y
    if yaxis_px is None: print("INFO: Y-axis point selection failed/cancelled. Exiting."); plt.close(fig); return
    yaxis_y_data = get_float_input("Enter Y data value at this Y-Axis point:", "Y-Axis Point Value", 1.0)
    if yaxis_y_data is None: print("INFO: Y-axis value input cancelled. Exiting."); plt.close(fig); return
    # Validation checks
    if np.allclose(np.array(origin_px), np.array(yaxis_px)):
         print("ERROR: Y-axis pixel location cannot be the same as the origin pixel.");
         root_err = _create_dialog_root(); tk.messagebox.showerror("Error", "Y-axis point cannot be the same pixel as the origin.", parent=root_err); root_err.destroy(); plt.close(fig); return
    if np.isclose(origin_y_data, yaxis_y_data):
         print("ERROR: Y-axis data value cannot be the same as the origin Y data value.");
         root_err = _create_dialog_root(); tk.messagebox.showerror("Error", "Y-axis data value cannot be the same as the origin Y value.", parent=root_err); root_err.destroy(); plt.close(fig); return
    is_log_y = get_axis_type("Y")
    if is_log_y and (origin_y_data <= 0 or yaxis_y_data <= 0):
        print("ERROR: Log Y-axis requires positive data values > 0.");
        root_err = _create_dialog_root(); tk.messagebox.showerror("Error", "Log scale requires Y values > 0 for Origin and Y-Axis point.", parent=root_err); root_err.destroy(); plt.close(fig); return
    print(f"INFO: Y-axis defined: px={yaxis_px}, data={yaxis_y_data}, log={is_log_y}")

    # --- 4. Data Acquisition Loop ---
    print("\n--- Ready for Data Acquisition ---")
    if fig is None or not plt.fignum_exists(fig.number):
        print("ERROR: Figure window closed before data acquisition loop start."); return

    show_instruction("4. LEFT-click data points. RIGHT/MIDDLE-click when FINISHED.")
    fig.canvas.manager.set_window_title("Image Digitizer - ACQUIRING DATA")
    acquired_data_points = []
    point_markers = [] # Keep track of plotted markers (optional: could be used for undo)

    while True:
        # Check if window was closed between clicks
        if fig is None or not plt.fignum_exists(fig.number):
            print("INFO: Window closed during data acquisition loop."); break

        clicked_points = None
        try:
            print("INFO: Waiting for data point ginput(1)... (Left-click point or Right/Middle-click finish)")
            clicked_points = plt.ginput(
                n=1, timeout=-1, show_clicks=True,
                mouse_add=plt.MouseButton.LEFT,
                mouse_stop=plt.MouseButton.RIGHT,
                mouse_pop=plt.MouseButton.MIDDLE
            )
            print(f"INFO: Data acquisition ginput returned: {clicked_points}")
        except Exception as e:
            print(f"ERROR: Error during data acquisition ginput: {e}")
            if ('destroyed' in str(e).lower()) or ('invalid command name' in str(e).lower()):
                 print("INFO: Window appears to have been closed during ginput.")
            else: print("ERROR: Unexpected error during ginput:"); traceback.print_exc()
            break # Exit loop on error

        # Check if user finished (right/middle click returns empty list)
        if not clicked_points:
            print("\nINFO: Data acquisition finished by user (right/middle click or window closed).")
            break # Exit loop

        # Process the left-clicked data point
        px, py = clicked_points[0]
        print(f"INFO: Data point clicked pixel: ({px:.1f}, {py:.1f})")

        # Plot marker for visual feedback
        marker, = ax.plot(px, py, 'r.', markersize=8) # Red dot
        point_markers.append(marker) # Store reference (e.g., for potential undo)
        fig.canvas.draw_idle() # Update display

        # Transform coordinates
        data_x, data_y = transform_coords(
            px, py,
            origin_px, xaxis_px, yaxis_px,
            origin_data, xaxis_x_data, yaxis_y_data,
            is_log_x, is_log_y
        )

        # Store and print valid data points
        if not (np.isnan(data_x) or np.isnan(data_y)):
            acquired_data_points.append((data_x, data_y))
            # Format output string for alignment
            print(f"  Point {len(acquired_data_points):>3}: X = {data_x:<12.6f}, Y = {data_y:<12.6f}")
        else:
            print(f"  Point skipped (pixel: ({px:.1f}, {py:.1f})) due to transformation issue (resulted in NaN).")
        # Instruction remains visible, loop continues for next point

    # --- Clear final instruction AFTER loop finishes ---
    show_instruction("")

    # --- 5. Save Data ---
    if not acquired_data_points:
        print("\nINFO: No data points were acquired. Nothing to save.")
    else:
        print(f"\nINFO: Acquired {len(acquired_data_points)} data points.")
        print("INFO: Prompting user for save file location...")
        root_sd = _create_dialog_root()
        # Suggest a filename with a timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"extracted_data_{timestamp}.txt"
        try:
            save_path = tk.filedialog.asksaveasfilename(
                master=root_sd,
                title="Save Extracted Data As",
                defaultextension=".txt",
                filetypes=[
                    ("Text Files", "*.txt"),
                    ("CSV Files", "*.csv"),
                    ("Excel Files", "*.xlsx"), # Added for clarity, though handled later
                    ("All Files", "*.*")
                ],
                initialfile=default_filename
            )
            print(f"INFO: Save file dialog returned: {save_path}")
        except Exception as e:
            print(f"ERROR: Exception during save file dialog: {e}"); traceback.print_exc()
            save_path = None
        finally:
            print("INFO: Destroying Tk root for save dialog.")
            root_sd.destroy()

        if save_path:
            base_name, original_ext = os.path.splitext(save_path)
            # Ensure primary save path uses .txt if user didn't specify or chose .xlsx initially
            txt_save_path = base_name + ".txt"

            # --- Save to TXT/CSV ---
            print(f"INFO: Saving data to TEXT file: {txt_save_path}")
            try:
                with open(txt_save_path, 'w', encoding='utf-8') as f:
                    # Write metadata header
                    f.write("# Extracted Data from Image Digitizer\n")
                    f.write(f"# Timestamp: {datetime.now().isoformat()}\n")
                    f.write(f"# Image: {os.path.basename(image_path)}\n")
                    f.write(f"# Origin (px): ({origin_px[0]:.2f}, {origin_px[1]:.2f}), "
                            f"Origin (data): ({origin_data[0]}, {origin_data[1]})\n")
                    f.write(f"# X-Axis Pt (px): ({xaxis_px[0]:.2f}, {xaxis_px[1]:.2f}), "
                            f"X-Axis Value: {xaxis_x_data}, Log: {is_log_x}\n")
                    f.write(f"# Y-Axis Pt (px): ({yaxis_px[0]:.2f}, {yaxis_px[1]:.2f}), "
                            f"Y-Axis Value: {yaxis_y_data}, Log: {is_log_y}\n")
                    f.write("#----------------------------------------\n")
                    f.write("# X_Data          Y_Data\n")
                    f.write("#----------------------------------------\n")
                    # Write data points
                    for x, y in acquired_data_points:
                        f.write(f"{x:<15.8g} {y:<15.8g}\n") # Use 'g' for general format
                print(f"INFO: Text data successfully saved.")
            except IOError as e:
                print(f"ERROR: Failed to write TEXT data file: {e}"); traceback.print_exc()
                root_err = _create_dialog_root(); tk.messagebox.showerror("Text Save Error", f"Failed to save text file:\n{e}", parent=root_err); root_err.destroy()
            except Exception as e: # Catch other potential errors
                print(f"ERROR: An unexpected error occurred during text save: {e}"); traceback.print_exc()
                root_err = _create_dialog_root(); tk.messagebox.showerror("Text Save Error", f"An unexpected error occurred saving text file:\n{e}", parent=root_err); root_err.destroy()

            # --- Save to Excel ---
            try:
                print("INFO: Preparing data for Excel export...")
                df = pd.DataFrame(acquired_data_points, columns=['X_Data', 'Y_Data'])
                # Use the same base name from user input for the Excel file
                excel_save_path = base_name + ".xlsx"
                print(f"INFO: Saving data to EXCEL file: {excel_save_path}")
                # Use openpyxl engine for .xlsx format
                df.to_excel(excel_save_path, index=False, engine='openpyxl')
                print(f"INFO: Excel data successfully saved.")
            except ImportError:
                 # Provide helpful message if pandas or openpyxl is missing
                 print("ERROR: Cannot save Excel. 'pandas' or 'openpyxl' library not found.")
                 error_msg = ("Could not save Excel file.\n"
                              "Please install required libraries:\n\n"
                              "pip install pandas openpyxl")
                 root_err = _create_dialog_root(); tk.messagebox.showwarning("Excel Save Error", error_msg, parent=root_err); root_err.destroy()
            except Exception as e:
                print(f"ERROR: Failed to save EXCEL data file: {e}"); traceback.print_exc()
                root_err = _create_dialog_root(); tk.messagebox.showerror("Excel Save Error", f"Failed to save Excel file:\n{e}", parent=root_err); root_err.destroy()
        else:
            print("INFO: Save cancelled by user.")

    # --- 6. Cleanup ---
    print("INFO: Cleaning up application...")
    show_instruction("") # Ensure instruction is gone before closing plot
    if fig is not None and plt.fignum_exists(fig.number):
        print("INFO: Closing Matplotlib figure.")
        plt.close(fig)
    else:
        print("INFO: Matplotlib figure already closed or never created.")
    print("INFO: Digitization process finished.")


# --- Main Execution Block ---
if __name__ == "__main__":
    print("Starting Image Digitizer Script...")
    # Ensure globals reset before each run (important for interactive/repeated runs)
    fig = None
    ax = None
    instruction_text_obj = None
    try:
        # Execute the main digitization process
        digitize_image()
    except Exception as e:
        # Catch any unexpected errors during the main execution
        print("\n--- An Unexpected Error Occurred ---")
        traceback.print_exc()
        # Attempt to show the error in a GUI dialog if Tkinter is still working
        try:
             root_fatal = _create_dialog_root()
             tk.messagebox.showerror(
                 "Fatal Error",
                 f"An unexpected error occurred:\n{e}\n\n"
                 "Please check the console output for details.",
                 parent=root_fatal
             )
             root_fatal.destroy()
        except Exception as tk_err:
            # If showing the Tkinter dialog fails, print to console
            print(f"Could not display fatal error in GUI (Tkinter error: {tk_err}).")
    finally:
        # --- Final Cleanup ---
        # Ensure any remaining Matplotlib plots are closed
        print("INFO: Closing any remaining figures.")
        plt.close('all') # Close all figures, just in case
    print("INFO: Script execution complete.")
