import tkinter as tk
from tkinter import filedialog, messagebox
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementNotInteractableException, NoSuchElementException
import os
import time
import base64
import threading
import webbrowser

# Global variables for image and output video folders, file list, and status
image_folder_path = ""
output_folder_path = ""
image_files = []
is_processing = False
stop_thread = False
delay_seconds = 10  # Default delay value

def select_image_folder():
    """Opens a dialog for the user to select the image folder."""
    global image_folder_path, image_files
    if is_processing:
        messagebox.showwarning("Warning", "Processing in progress, please wait.")
        return

    selected_path = filedialog.askdirectory(title="Select Image Folder")

    if selected_path:
        image_folder_path = selected_path
        image_files = [
            os.path.join(image_folder_path, f)
            for f in os.listdir(image_folder_path)
            if f.lower().endswith(('.png', '.jpg', '.jpeg'))
        ]
        
        if image_files:
            label_status.config(text=f"Selected {len(image_files)} image files.")
        else:
            label_status.config(text="No image files found in the folder.", fg="red")
    else:
        label_status.config(text="No folder selected.", fg="gray")

def select_output_folder():
    """Opens a dialog for the user to select the video output folder."""
    global output_folder_path
    if is_processing:
        messagebox.showwarning("Warning", "Processing in progress, please wait.")
        return

    selected_path = filedialog.askdirectory(title="Select Output Video Folder")
    if selected_path:
        output_folder_path = selected_path
        label_output_status.config(text=f"Output folder: {os.path.basename(output_folder_path)}")
    else:
        label_output_status.config(text="No output folder selected.")

def generate_video_task():
    """
    This function runs in a separate thread to automate the browser in headless and incognito mode.
    """
    global is_processing, stop_thread
    is_processing = True
    stop_thread = False

    chrome_options = Options()
    chrome_options.add_argument("--incognito")
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        wait = WebDriverWait(driver, 120)

        description = text_description.get("1.0", tk.END).strip()
        
        for i, image_path in enumerate(image_files):
            if stop_thread:
                update_gui_status("Processing stopped by user.", "orange")
                break
                
            update_gui_status(f"Processing image {i+1}/{len(image_files)}: {os.path.basename(image_path)}", "blue")
            
            try:
                driver.get("https://vheer.com/app/image-to-video")
                
                input_element = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='file']")))
                input_element.send_keys(os.path.abspath(image_path))
                
                description_element = wait.until(EC.presence_of_element_located((By.XPATH, "//textarea[@placeholder='Input image description here or use the prompts generator']")))
                description_element.clear()
                description_element.send_keys(description)
                
                generate_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[text()='Generate']")))
                generate_button.click()

                update_gui_status(f"Waiting for video for image {os.path.basename(image_path)}...", "darkorange")
                
                wait.until(EC.invisibility_of_element_located((By.XPATH, "//div[@aria-label='loading']")))
                time.sleep(5)

                update_gui_status(f"Downloading video for image {os.path.basename(image_path)}...", "purple")
                
                video_element = wait.until(EC.presence_of_element_located((By.TAG_NAME, "video")))
                video_url = video_element.get_attribute("src")

                script = """
                    var blobUrl = arguments[0];
                    var callback = arguments[arguments.length - 1];
                    var xhr = new XMLHttpRequest();
                    xhr.onload = function() {
                        var reader = new FileReader();
                        reader.onloadend = function() {
                            callback(reader.result);
                        };
                        reader.readAsDataURL(xhr.response);
                    };
                    xhr.open('GET', blobUrl);
                    xhr.responseType = 'blob';
                    xhr.send();
                """
                
                video_data_url = driver.execute_async_script(script, video_url)
                video_data = base64.b64decode(video_data_url.split(',')[1])

                image_name = os.path.splitext(os.path.basename(image_path))[0]
                file_name = f"video_{image_name}.mp4"
                file_path = os.path.join(output_folder_path, file_name)
                
                with open(file_path, "wb") as f:
                    f.write(video_data)
                
                update_gui_status(f"Video successfully downloaded for image: {image_name}.", "green")

                # Add delay between generations
                if i < len(image_files) - 1:
                    update_gui_status(f"Pausing for {delay_seconds} seconds...", "orange")
                    time.sleep(delay_seconds)
                
            except (TimeoutException, ElementNotInteractableException, NoSuchElementException) as e:
                update_gui_status(f"Error processing image {os.path.basename(image_path)}: {e}. Skipping and continuing.", "red")
                continue
            
    except Exception as e:
        update_gui_status(f"A serious error occurred: {e}", "red")
    finally:
        if driver:
            driver.quit()
        is_processing = False
        if not stop_thread:
            update_gui_status("Completed! Ready", "green")
        button_generate.config(state=tk.NORMAL)
        button_stop.config(state=tk.DISABLED)

def update_gui_status(text, color):
    """Safely updates the GUI status from another thread."""
    root.after(0, label_status.config, {"text": text, "fg": color})

def start_generation_thread():
    """Starts a new thread to run the video generation task."""
    global stop_thread, delay_seconds
    if is_processing:
        return

    if not image_files:
        messagebox.showerror("Error", "Please select an image folder first.")
        return
        
    if not output_folder_path:
        messagebox.showerror("Error", "Please select an output video folder first.")
        return

    try:
        delay_seconds = int(entry_delay.get())
        if delay_seconds < 0:
            raise ValueError
    except ValueError:
        messagebox.showerror("Error", "Delay must be a non-negative integer.")
        return

    description = text_description.get("1.0", tk.END).strip()
    if not description:
        messagebox.showerror("Error", "You must enter a description for the images.")
        return

    button_generate.config(state=tk.DISABLED)
    button_stop.config(state=tk.NORMAL)
    
    process_thread = threading.Thread(target=generate_video_task)
    process_thread.start()

def stop_generation():
    """Sets a flag to stop the processing thread."""
    global stop_thread
    stop_thread = True
    update_gui_status("Stop request received, please wait...", "orange")
    button_stop.config(state=tk.DISABLED)

def open_link(url):
    """Opens a URL in the default web browser."""
    webbrowser.open_new(url)

# --- Create the Tkinter User Interface ---

root = tk.Tk()
root.title("Batch Video Generation Automation from Multiple Images")
root.geometry("800x420")
root.configure(padx=20, pady=20)

# 1. Add select image folder button
frame_image = tk.Frame(root)
frame_image.pack(fill="x", pady=5)
button_select = tk.Button(frame_image, text="Select Image Folder", command=select_image_folder)
button_select.pack(side="left", padx=5)
label_status = tk.Label(frame_image, text="No folder selected.", fg="gray")
label_status.pack(side="left", padx=5)

# 2. Add select output video folder button
frame_output = tk.Frame(root)
frame_output.pack(fill="x", pady=5)
button_select_output = tk.Button(frame_output, text="Select Output Video Folder", command=select_output_folder)
button_select_output.pack(side="left", padx=5)
label_output_status = tk.Label(frame_output, text="No output folder selected.", fg="gray")
label_output_status.pack(side="left", padx=5)

# 3. Add description text box
label_description = tk.Label(root, text="Description for all images:")
label_description.pack(fill="x")
text_description = tk.Text(root, height=8, wrap="word")
text_description.pack(fill="x", pady=5)
# Set default description
text_description.insert(tk.END, "make a video, move and be smile")

# 4. Add delay input field
frame_delay = tk.Frame(root)
frame_delay.pack(fill="x", pady=5)
label_delay = tk.Label(frame_delay, text="Delay between generations (seconds):")
label_delay.pack(side="left", padx=5)
entry_delay = tk.Entry(frame_delay)
entry_delay.insert(0, "10")  # Default value
entry_delay.pack(side="left", padx=5)

# 5. Add control buttons
frame_buttons = tk.Frame(root)
frame_buttons.pack(fill="x", pady=15)
button_generate = tk.Button(frame_buttons, text="Generate Video", command=start_generation_thread)
button_generate.pack(side="left", expand=True, padx=5)
button_stop = tk.Button(frame_buttons, text="Stop", command=stop_generation, state=tk.DISABLED)
button_stop.pack(side="left", expand=True, padx=5)

# 6. Add account info label
label_account_info = tk.Label(
    root,
    text="VPBANK (VIETNAM) - SWIFT/BIC: VPBKVNVX - ACCOUNT NUMBER: 155081748 . THANKS",
    fg="blue",
    font=("Arial", 12)
)
label_account_info.pack(side="bottom", fill="x", pady=(10, 0))

# 7. Add donation link label
label_bottom_link = tk.Label(
    root,
    text="CLICK LINK TO DONATE ME: https://buymeacoffee.com/htt117",
    fg="red",
    font=("Arial", 16, "bold"),
    cursor="hand2"
)
label_bottom_link.pack(side="bottom", fill="x", pady=(10, 0))

label_bottom_link.bind(
    "<Button-1>",
    lambda e: open_link("https://buymeacoffee.com/htt117")
)

root.mainloop()