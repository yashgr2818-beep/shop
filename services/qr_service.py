import qrcode
import os
import socket

def get_local_ip():
    """Detects active network IPs prioritizing Mobile Hotspot (192.168.137.x) or Wi-Fi."""
    try:
        hostname = socket.gethostname()
        all_ips = socket.gethostbyname_ex(hostname)[2]
        # Prioritize Hotspot IP if active
        for ip in all_ips:
            if ip.startswith('192.168.137.'):
                return ip
        # Otherwise return first LAN IP
        for ip in all_ips:
            if not ip.startswith('127.'):
                return ip
    except Exception:
        pass

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def generate_shop_qr(shop_slug, qr_folder, base_url=None):
    """Generate permanent QR code for the shop.
    Supports Render.com production URL, custom base URL, or local LAN/Hotspot IP.
    """
    if not base_url:
        render_url = os.environ.get('RENDER_EXTERNAL_URL')
        if render_url:
            base_url = render_url.rstrip('/')
        else:
            host_ip = get_local_ip()
            base_url = f"http://{host_ip}:5000"
    else:
        base_url = base_url.rstrip('/')

    url = f"{base_url}/shop/{shop_slug}"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    filepath = os.path.join(qr_folder, f"{shop_slug}.png")
    img.save(filepath)
    return f"{shop_slug}.png"
