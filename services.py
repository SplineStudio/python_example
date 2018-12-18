import uuid
import qrcode
import urllib
import os
import base64

from io import BytesIO
from django.conf import settings


class QR:
    def __init__(self, model, instance):
        self.model = model
        self.instance = instance
        self.token = ''
        self.url = ''
        self.path = 'static/qr/'
        self.qr_format = '.png'
        self.img = ''

    def generate_qr(self):
        self.check_dir()
        self.token = self.generate_token()
        if not bool(self.instance.qr_code):
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=50,
                border=5,
            )
            qr.add_data(self.token)
            qr.make(fit=True)
            self.img = qr.make_image(fill_color="black", back_color="white")
            img2 = self.img
            buffered = BytesIO()
            img2.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue())
            self.instance.qr_code = 'data:image/png;base64,' + img_str.decode('utf-8')
            self.instance.uid = self.token
        self.token = self.instance.uid
        self.url = urllib.parse.unquote(urllib.parse.unquote(self.instance.qr_code.url))
        return self.token, self.url

    def generate_token(self):
        token = uuid.uuid4().hex[:40].upper()
        op = self.model.objects.filter(uid=token).first()
        if op is None:
            return token
        else:
            self.generate_token()

    def check_dir(self):
        abs_path = "{}/{}".format(settings.BASE_DIR, self.path)
        if not os.path.exists(abs_path):
            os.mkdir(abs_path)

    def save_img(self):
        if isinstance(self.img, str):
            return self.img
        self.img.save('{}{}{}'.format(self.path, self.token, self.qr_format))
        return "{}/{}{}{}".format(settings.URL, self.path, self.token, self.qr_format)
