import tkinter as tk
from tkinter import filedialog, messagebox
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import time
import base64
import threading

# Biến toàn cục để lưu đường dẫn tệp ảnh
image_path = ""

def select_image_path():
    """Mở hộp thoại để người dùng chọn tệp ảnh."""
    global image_path
    image_path = filedialog.askopenfilename(
        title="Chọn tệp ảnh",
        filetypes=(("Tệp ảnh", "*.jpg *.jpeg *.png"), ("Tất cả các tệp", "*.*"))
    )
    if image_path:
        label_status.config(text=f"Đã chọn tệp: {os.path.basename(image_path)}")

def generate_video_task():
    """
    Hàm này chạy trong một luồng riêng để tự động hóa trình duyệt.
    Nó bao gồm toàn bộ quá trình Selenium.
    """
    global image_path
    
    # Cập nhật trạng thái
    update_gui_status("Đang xử lý, vui lòng chờ...", "blue")

    # Khởi tạo đối tượng Options
    chrome_options = Options()

    # Thêm tham số để chạy ở chế độ ẩn danh (incognito)
    chrome_options.add_argument("--incognito")
    # Thêm tham số để chạy ở chế độ ngầm (headless)
    chrome_options.add_argument("--headless")
    # Thêm tham số để giải quyết một số vấn đề thường gặp với chế độ headless
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Thiết lập thời gian chờ tối đa
    wait = WebDriverWait(driver, 600)

    try:
        # Mở trang web và chờ các phần tử đầu tiên xuất hiện
        driver.get("https://vheer.com/app/image-to-video")
        wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='file']")))

        # Tải ảnh lên
        input_element = driver.find_element(By.XPATH, "//input[@type='file']")
        input_element.send_keys(os.path.abspath(image_path))
        
        # Nhập mô tả
        description_element = wait.until(EC.presence_of_element_located((By.XPATH, "//textarea[@placeholder='Input image description here or use the prompts generator']")))
        description_element.send_keys(entry_description.get())

        # Nhấn nút "Generate"
        generate_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[text()='Generate']")))
        generate_button.click()

        # Chờ quá trình tạo video hoàn tất
        update_gui_status("Đang chờ video được tạo...", "darkorange")
        wait.until(EC.invisibility_of_element_located((By.XPATH, "//div[@aria-label='loading']")))
        
        # Cập nhật trạng thái và chờ 10 giây
        update_gui_status("Video đã được tạo thành công! Đang chờ 10 giây...", "green")
        time.sleep(10)

        # Tải video về
        update_gui_status("Đang tải video về...", "purple")
        
        video_element = wait.until(EC.presence_of_element_located((By.TAG_NAME, "video")))
        video_url = video_element.get_attribute("src")

        # Sử dụng JavaScript không đồng bộ để tải dữ liệu blob về
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
        
        # Thực thi JavaScript và đợi kết quả trả về
        video_data_url = driver.execute_async_script(script, video_url)
        
        # Giải mã chuỗi Base64 và lưu tệp
        video_data = base64.b64decode(video_data_url.split(',')[1])

        file_name = f"video_{int(time.time())}.mp4"
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), file_name)
        
        with open(file_path, "wb") as f:
            f.write(video_data)
        
        update_gui_status(f"Đã tải video thành công: {file_name}", "green")

    except Exception as e:
        update_gui_status(f"Đã xảy ra lỗi: {e}", "red")
        
    finally:
        update_gui_status("Sẵn sàng", "green")
        button_generate.config(state=tk.NORMAL)
        driver.quit()

def update_gui_status(text, color):
    """Cập nhật trạng thái giao diện một cách an toàn từ luồng khác."""
    root.after(0, label_status.config, {"text": text, "fg": color})

def start_generation_thread():
    """Bắt đầu một luồng mới để chạy tác vụ tạo video."""
    if not image_path:
        messagebox.showerror("Lỗi", "Vui lòng chọn một tệp ảnh trước.")
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
root.title("Tự động hóa tạo video")
root.geometry("400x300")
root.configure(padx=20, pady=20)

# 1. Thêm nút chọn ảnh
frame_image = tk.Frame(root)
frame_image.pack(fill="x", pady=10)
button_select = tk.Button(frame_image, text="Chọn ảnh", command=select_image_path)
button_select.pack(side="left", padx=5)

label_status = tk.Label(frame_image, text="Chưa có ảnh được chọn.", fg="gray")
label_status.pack(side="left", padx=5)

# 2. Thêm ô nhập mô tả
label_description = tk.Label(root, text="Mô tả ảnh:")
label_description.pack(fill="x")
entry_description = tk.Entry(root)
entry_description.pack(fill="x", pady=5)

# 3. Thêm nút tạo video
button_generate = tk.Button(root, text="Tạo video", command=start_generation_thread)
button_generate.pack(fill="x", pady=15)

# Chạy vòng lặp sự kiện chính của Tkinter
root.mainloop()