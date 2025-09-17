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
import webbrowser

# Biến toàn cục để lưu đường dẫn thư mục, danh sách tệp ảnh và trạng thái
image_folder_path = ""
image_files = []
is_processing = False
stop_thread = False

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
            for f in os.path.listdir(image_folder_path) 
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
    global image_files, is_processing, stop_thread
    is_processing = True
    stop_thread = False

    chrome_options = Options()
    chrome_options.add_argument("--incognito")
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = None
    service = Service(ChromeDriverManager().install())
    
    description = text_description.get("1.0", tk.END).strip()
    
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        wait = WebDriverWait(driver, 120)

        for i, image_path in enumerate(image_files):
            if stop_thread:
                update_gui_status("Đã dừng quá trình xử lý.", "orange")
                break
                
            update_gui_status(f"Đang xử lý ảnh {i+1}/{len(image_files)}: {os.path.basename(image_path)}", "blue")
            
            driver.get("https://vheer.com/app/image-to-video")
            
            try:
                input_element = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='file']")))
                input_element.send_keys(os.path.abspath(image_path))
                
                description_element = wait.until(EC.presence_of_element_located((By.XPATH, "//textarea[@placeholder='Input image description here or use the prompts generator']")))
                description_element.send_keys(description)
                
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
        if not stop_thread:
            update_gui_status("Hoàn thành! Sẵn sàng", "green")
        button_generate.config(state=tk.NORMAL)
        button_stop.config(state=tk.DISABLED)

def update_gui_status(text, color):
    """Cập nhật trạng thái giao diện một cách an toàn từ luồng khác."""
    root.after(0, label_status.config, {"text": text, "fg": color})

def start_generation_thread():
    """Bắt đầu một luồng mới để chạy tác vụ tạo video."""
    global stop_thread
    if is_processing:
        return

    if not image_files:
        messagebox.showerror("Lỗi", "Vui lòng chọn một thư mục chứa ảnh trước.")
        return

    description = text_description.get("1.0", tk.END).strip()
    if not description:
        messagebox.showerror("Lỗi", "Bạn phải nhập mô tả cho ảnh.")
        return

    button_generate.config(state=tk.DISABLED)
    button_stop.config(state=tk.NORMAL)
    
    process_thread = threading.Thread(target=generate_video_task)
    process_thread.start()

def stop_generation():
    """Đặt biến cờ để dừng luồng xử lý."""
    global stop_thread
    stop_thread = True
    update_gui_status("Đang yêu cầu dừng, vui lòng chờ...", "orange")
    button_stop.config(state=tk.DISABLED)

def open_link(url):
    """Mở một URL trong trình duyệt web mặc định."""
    webbrowser.open_new(url)

# --- Tạo Giao diện người dùng với Tkinter ---

root = tk.Tk()
root.title("Tự động hóa tạo video hàng loạt")
root.geometry("800x420")
root.configure(padx=20, pady=20)

# 1. Thêm nút chọn thư mục ảnh
frame_image = tk.Frame(root)
frame_image.pack(fill="x", pady=10)
button_select = tk.Button(frame_image, text="Chọn thư mục ảnh", command=select_image_folder)
button_select.pack(side="left", padx=5)

label_status = tk.Label(frame_image, text="Chưa có thư mục nào được chọn.", fg="gray")
label_status.pack(side="left", padx=5)

# 2. Thêm ô nhập mô tả (Text thay cho Entry)
label_description = tk.Label(root, text="Mô tả cho tất cả các ảnh:")
label_description.pack(fill="x")
text_description = tk.Text(root, height=8, wrap="word")
text_description.pack(fill="x", pady=5)

# 3. Thêm các nút điều khiển
frame_buttons = tk.Frame(root)
frame_buttons.pack(fill="x", pady=15)

button_generate = tk.Button(frame_buttons, text="Tạo video", command=start_generation_thread)
button_generate.pack(side="left", expand=True, padx=5)

button_stop = tk.Button(frame_buttons, text="Dừng chạy", command=stop_generation, state=tk.DISABLED)
button_stop.pack(side="left", expand=True, padx=5)


# 5. Thêm nhãn thông tin tài khoản
label_account_info = tk.Label(
    root,
    text="VPBANK (VIETNAM) - SWIFT/BIC: VPBKVNVX - ACCOUNT NUMBER: 155081748 . THANKS",
    fg="blue",
    font=("Arial", 12)
)
label_account_info.pack(side="bottom", fill="x", pady=(10, 0))

# 6. Thêm nhãn liên kết mới (đây là phần bạn muốn thêm)
label_bottom_link = tk.Label(
    root,
    text="CLICK LINK TO DONATE ME: https://buymeacoffee.com/htt117",
    fg="red",
    font=("Arial", 16, "bold"),
    cursor="hand2"
)
label_bottom_link.pack(side="bottom", fill="x", pady=(10, 0))

# Gán sự kiện click cho nhãn
label_bottom_link.bind(
    "<Button-1>",
    lambda e: open_link("https://www.facebook.com/your.username")
)

# Chạy vòng lặp sự kiện chính của Tkinter
root.mainloop()