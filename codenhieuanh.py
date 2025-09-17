import tkinter as tk
from tkinter import filedialog, messagebox
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementNotInteractableException
import os
import time
import base64
import threading

# Biến toàn cục để lưu đường dẫn thư mục và danh sách tệp ảnh
image_folder_path = ""
image_files = []
is_processing = False

def select_image_folder():
    """Mở hộp thoại để người dùng chọn thư mục chứa ảnh."""
    global image_folder_path, image_files
    if is_processing:
        messagebox.showwarning("Cảnh báo", "Đang xử lý, vui lòng chờ hoàn thành.")
        return

    image_folder_path = filedialog.askdirectory(title="Chọn thư mục chứa ảnh")
    
    if image_folder_path:
        # Lấy danh sách các tệp ảnh từ thư mục đã chọn
        image_files = [
            os.path.join(image_folder_path, f) 
            for f in os.listdir(image_folder_path) 
            if f.lower().endswith(('.png', '.jpg', '.jpeg'))
        ]
        
        if image_files:
            label_status.config(text=f"Đã chọn {len(image_files)} tệp ảnh.")
        else:
            label_status.config(text="Không tìm thấy tệp ảnh nào trong thư mục.", fg="red")

def generate_video_task():
    """
    Hàm này chạy trong một luồng riêng để tự động hóa trình duyệt ở chế độ ẩn.
    """
    global image_files, is_processing
    is_processing = True

    # Khởi tạo đối tượng Options và các tham số cần thiết
    chrome_options = Options()
    chrome_options.add_argument("--incognito")
    chrome_options.add_argument("--headless")  # Dòng này kích hoạt chế độ chạy ngầm
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = None
    service = Service(ChromeDriverManager().install())
    
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        wait = WebDriverWait(driver, 120)

        # Lặp qua từng tệp ảnh trong danh sách
        for i, image_path in enumerate(image_files):
            update_gui_status(f"Đang xử lý ảnh {i+1}/{len(image_files)}: {os.path.basename(image_path)}", "blue")
            
            driver.get("https://vheer.com/app/image-to-video")
            
            try:
                input_element = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='file']")))
                input_element.send_keys(os.path.abspath(image_path))
                
                description_element = wait.until(EC.presence_of_element_located((By.XPATH, "//textarea[@placeholder='Input image description here or use the prompts generator']")))
                description_element.send_keys(entry_description.get())
                
                generate_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[text()='Generate']")))
                generate_button.click()

                update_gui_status(f"Đang chờ video cho ảnh {os.path.basename(image_path)}...", "darkorange")
                wait.until(EC.invisibility_of_element_located((By.XPATH, "//div[@aria-label='loading']")))
                
                time.sleep(5)

                update_gui_status(f"Đang tải video về cho ảnh {os.path.basename(image_path)}...", "purple")
                
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
                file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), file_name)
                
                with open(file_path, "wb") as f:
                    f.write(video_data)
                
                update_gui_status(f"Đã tải video thành công cho ảnh: {image_name}. Tiếp theo...", "green")
                
            except (TimeoutException, ElementNotInteractableException) as e:
                update_gui_status(f"Lỗi khi xử lý ảnh {os.path.basename(image_path)}: {e}. Bỏ qua và tiếp tục.", "red")
                continue
            
    except Exception as e:
        update_gui_status(f"Đã xảy ra lỗi nghiêm trọng: {e}", "red")
    finally:
        if driver:
            driver.quit()
        is_processing = False
        update_gui_status("Hoàn thành! Sẵn sàng", "green")
        button_generate.config(state=tk.NORMAL)

def update_gui_status(text, color):
    """Cập nhật trạng thái giao diện một cách an toàn từ luồng khác."""
    root.after(0, label_status.config, {"text": text, "fg": color})

def start_generation_thread():
    """Bắt đầu một luồng mới để chạy tác vụ tạo video."""
    if is_processing:
        return

    if not image_files:
        messagebox.showerror("Lỗi", "Vui lòng chọn một thư mục chứa ảnh trước.")
        return

    description = entry_description.get()
    if not description:
        messagebox.showerror("Lỗi", "Bạn phải nhập mô tả cho ảnh.")
        return

    # Vô hiệu hóa nút để tránh người dùng nhấn lại
    button_generate.config(state=tk.DISABLED)
    
    # Tạo và chạy một luồng mới cho hàm generate_video_task
    process_thread = threading.Thread(target=generate_video_task)
    process_thread.start()

# --- Tạo Giao diện người dùng với Tkinter ---

root = tk.Tk()
root.title("Tự động hóa tạo video hàng loạt")
root.geometry("450x300")
root.configure(padx=20, pady=20)

# 1. Thêm nút chọn thư mục ảnh
frame_image = tk.Frame(root)
frame_image.pack(fill="x", pady=10)
button_select = tk.Button(frame_image, text="Chọn thư mục ảnh", command=select_image_folder)
button_select.pack(side="left", padx=5)

label_status = tk.Label(frame_image, text="Chưa có thư mục nào được chọn.", fg="gray")
label_status.pack(side="left", padx=5)

# 2. Thêm ô nhập mô tả
label_description = tk.Label(root, text="Mô tả cho tất cả các ảnh:")
label_description.pack(fill="x")
entry_description = tk.Entry(root)
entry_description.pack(fill="x", pady=5)

# 3. Thêm nút tạo video
button_generate = tk.Button(root, text="Tạo video hàng loạt", command=start_generation_thread)
button_generate.pack(fill="x", pady=15)

# Chạy vòng lặp sự kiện chính của Tkinter
root.mainloop()