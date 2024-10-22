from django.core.exceptions import ValidationError
from django.contrib import messages
from django.db import models
from datetime import datetime, timedelta
from django.utils import timezone
from django.urls import reverse
import subprocess
import string, random, os, math

class Clients(models.Model):
    IP_Address = models.CharField(max_length=15, verbose_name='IP')
    MAC_Address = models.CharField(max_length=255, verbose_name='MAC Address', unique=True)
    Device_Name = models.CharField(max_length=255, verbose_name='Device Name', null=True, blank=True)
    Time_Left = models.DurationField(default=timezone.timedelta(minutes=0))
    Expire_On = models.DateTimeField(null=True, blank=True)
    Upload_Rate = models.IntegerField(verbose_name='Upload Bandwidth', help_text='Specify client internet upload bandwidth in Kbps. No value = unlimited bandwidth', null=True, blank=True )
    Download_Rate = models.IntegerField(verbose_name='Download Bandwidth', help_text='Specify client internet download bandwidth in Kbps. No value = unlimited bandwidth', null=True, blank=True )
    Notification_ID = models.CharField(verbose_name = 'Notification ID', max_length=255, null=True, blank = True)
    Notified_Flag = models.BooleanField(default=False)
    Date_Created = models.DateTimeField(default=timezone.now)


    @property
    def running_time(self):
        if not self.Expire_On:
            return timedelta(0)
        else:
            running_time = self.Expire_On - timezone.now()
            if running_time < timedelta(0):
                return timedelta(0)
            else:
                return running_time

    @property
    def Connection_Status(self):
        if self.running_time > timedelta(0):
            return 'Connected'
        else:
            if self.Time_Left > timedelta(0):
                return 'Paused'
            else:
                return 'Disconnected'

    def Connect(self, add_time = timedelta(0)):
        total_time = self.Time_Left + add_time
        success_flag = False
        if total_time > timedelta(0):
            if self.running_time > timedelta(0):
                self.Expire_On = self.Expire_On + total_time
            else:
                self.Expire_On = timezone.now() + total_time

            self.Time_Left = timedelta(0)

            push_notif = PushNotifications.objects.get(pk=1)
            push_trigger_time = push_notif.notification_trigger_time

            if (total_time + self.running_time) > push_trigger_time and self.Notified_Flag == True:
                self.Notified_Flag = False

            self.save()

            success_flag = True
        return success_flag

    def Disconnect(self):
        success_flag = False
        if self.Connection_Status == 'Connected':
            self.Expire_On = None
            self.Time_Left = timedelta(0)
            self.Notified_Flag = False
            self.save()
            success_flag = True
        return success_flag

    def Pause(self):
        success_flag = False
        if self.Connection_Status == 'Connected':
            self.Time_Left = self.running_time
            self.Expire_On = None
            self.save()
            success_flag = True
        return success_flag

    class Meta:
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'

    def __str__(self):
        return str(self.IP_Address) + ' | ' + str(self.MAC_Address)

class Whitelist(models.Model):
    MAC_Address = models.CharField(max_length=255, verbose_name='MAC', unique=True)
    Device_Name = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = 'Allowed Client'
        verbose_name_plural = 'Allowed Clients'

    def __str__(self):
        name =  self.MAC_Address if not self.Device_Name else self.Device_Name
        return 'Device: ' + name


class Ledger(models.Model):
    Date = models.DateTimeField()
    Client = models.CharField(max_length=50)
    Denomination = models.IntegerField()
    Slot_No = models.IntegerField()

    def save(self, *args, **kwargs):
        self.Date = timezone.now()
        super(Ledger, self).save(*args, **kwargs)

    class Meta:
        verbose_name = 'Ledger'
        verbose_name_plural = 'Ledger'

    def __str__(self):
        return 'Transaction no: ' + str(self.pk)


class CoinSlot(models.Model):
    def generate_code(size=10):
        found = False
        random_code = None

        while not found:
            random_code = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(size))
            count = Vouchers.objects.filter(Voucher_code=random_code).count()
            if count == 0:
                found = True

        return random_code

    Edit = 'Edit'
    Client = models.CharField(max_length=17, null=True, blank=True)
    Last_Updated = models.DateTimeField(null=True, blank=True)
    Slot_ID = models.CharField(default=generate_code, unique=True, max_length=10, null=False, blank=False)
    Slot_Address = models.CharField(unique=True, max_length=17, null=False, blank=False, default='00:00:00:00:00:00')
    Slot_Desc = models.CharField(max_length=50, null=True, blank=True, verbose_name='Description')

    class Meta:
        verbose_name = 'Coin Slot'
        verbose_name_plural = 'Coin Slot'

    def __str__(self):

        return 'Slot no: ' + str(self.pk)

class Rates(models.Model):
    Edit = "Edit"
    Denom = models.IntegerField(verbose_name='Denomination', help_text="Coin denomination corresponding to specified coinslot pulse.")
    Pulse = models.IntegerField(blank=True, null=True, help_text="Coinslot pulse count corresponding to coin denomination. Leave it blank for promotional rates.")
    Minutes = models.DurationField(verbose_name='Duration', default=timezone.timedelta(minutes=0), help_text='Internet access duration in hh:mm:ss format')

    class Meta:
        verbose_name = "Rate"
        verbose_name_plural = "Rates"

    def __str__(self):
        return 'Rate: ' + str(self.Denom)


class CoinQueue(models.Model):
    Client = models.CharField(max_length=17, null=True, blank=True)
    Total_Coins = models.IntegerField(null=True, blank=True, default=0)

    @property
    def Total_Time(self):
        settings = Settings.objects.get(pk=1)
        rate_type = settings.Rate_Type
        base_value = settings.Base_Value
        total_coins = self.Total_Coins
        total_time = timedelta(0)

        if rate_type == 'manual':
            rates = Rates.objects.all().order_by('-Denom')
            for rate in rates:
                multiplier = math.floor(total_coins/rate.Denom)
                if multiplier > 0:
                    total_coins = total_coins - (rate.Denom * multiplier)
                    total_time = total_time + (rate.Minutes * multiplier)
        
        if rate_type == 'auto':
            total_time = base_value * total_coins
        
        return total_time

    class Meta:
        verbose_name = 'Coin Queue'
        verbose_name_plural = 'Coin Queue'

    def __str__(self):
        if self.Client:
            return 'Coin queue for: ' + self.Client
        else:
            return 'Record'


class Settings(models.Model):
    rate_type_choices = (
        ('auto', 'Minutes/Peso'),
        ('manual', 'Custom Rate'),
    )
    enable_disable_choices = (
        (1, 'Enable'),
        (0, 'Disable'),
    )

    def get_image_path(instance, filename):
        return os.path.join(str(instance.id), filename)

    Hotspot_Name = models.CharField(max_length=255)
    Hotspot_Address = models.CharField(max_length=255, null=True, blank=True)
    BG_Image = models.ImageField(upload_to=get_image_path, blank=True, null=True)
    Slot_Timeout = models.IntegerField(help_text='Slot timeout in seconds.')
    Rate_Type = models.CharField(max_length=25, default="auto", choices=rate_type_choices, help_text='Select "Minutes/Peso" to use  Minutes / Peso value, else use "Custom Rate" to manually setup Rates based on coin value.')
    Base_Value = models.DurationField(default=timezone.timedelta(minutes=0), verbose_name='Minutes / Peso')
    Inactive_Timeout = models.IntegerField(verbose_name='Inactive Timeout', help_text='Timeout before an idle client (status = Disconnected) is removed from the client list. (Minutes)')
    Redir_Url = models.CharField(max_length=255, verbose_name='Redirect URL', help_text='Redirect url after a successful login. If not set, will default to the timer page.', null=True, blank=True)
    Vouchers_Flg = models.IntegerField(verbose_name='Vouchers', default=1, choices=enable_disable_choices, help_text='Enables voucher module.')
    Pause_Resume_Flg = models.IntegerField(verbose_name='Pause/Resume', default=1, choices=enable_disable_choices, help_text='Enables pause/resume function.')
    Disable_Pause_Time = models.DurationField(default=timezone.timedelta(minutes=0), null=True, blank=True, help_text='Disables Pause time button if remaining time is less than the specified time hh:mm:ss format.')
    Coinslot_Pin = models.IntegerField(verbose_name='Coinslot Pin', help_text='Please refer raspberry/orange pi GPIO.BOARD pinout.', null=True, blank=True)
    Light_Pin = models.IntegerField(verbose_name='Light Pin', help_text='Please refer raspberry/orange pi GPIO.BOARD pinout.', null=True, blank=True)

    def clean(self, *args, **kwargs):
        if self.Coinslot_Pin or self.Light_Pin:
            if self.Coinslot_Pin == self.Light_Pin:
                raise ValidationError('Coinslot Pin should not be the same as Light Pin.')

    class Meta:
        verbose_name = 'Settings'

    def __str__(self):
        return 'Settings'

class Network(models.Model):
    Edit = "Edit"
    Server_IP = models.GenericIPAddressField(verbose_name='Server IP', protocol='IPv4', default='10.0.0.1', null=False, blank=False)
    Netmask = models.GenericIPAddressField(protocol='IPv4', default='255.255.255.0', null=False, blank=False)
    DNS_1 = models.GenericIPAddressField(protocol='IPv4', verbose_name='DNS 1', default='8.8.8.8', null=False, blank=False)
    DNS_2 = models.GenericIPAddressField(protocol='IPv4', verbose_name='DNS 2 (Optional)', default='8.8.4.4', null=True, blank=True)
    Upload_Rate = models.IntegerField(verbose_name='Upload Bandwidth', help_text='Specify global internet upload bandwidth in Kbps. No value = unlimited bandwidth', null=True, blank=True )
    Download_Rate = models.IntegerField(verbose_name='Download Bandwidth', help_text='Specify global internet download bandwidth in Kbps. No value = unlimited bandwidth', null=True, blank=True )

    class Meta:
        verbose_name = 'Network'

    def __str__(self):
        return 'Network Settings'


class Vouchers(models.Model):
    status_choices = (
        ('Used', 'Used'),
        ('Not Used', 'Not Used'),
        ('Expired', 'Expired')
    )

    def generate_code(size=6):
        found = False
        random_code = None

        while not found:
            random_code = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(size))
            count = Vouchers.objects.filter(Voucher_code=random_code).count()
            if count == 0:
                found = True

        return random_code

    Voucher_code = models.CharField(default=generate_code, max_length=20, null=False, blank=False, unique=True)
    Voucher_status = models.CharField(verbose_name='Status', max_length=25, choices=status_choices, default='Not Used', null=False, blank=False)
    Voucher_client = models.CharField(verbose_name='Client', max_length=50, null=True, blank=True, help_text="Voucher code user. * Optional")
    Voucher_create_date_time = models.DateTimeField(verbose_name='Created Date/Time', auto_now_add=True)
    Voucher_used_date_time = models.DateTimeField(verbose_name='Used Date/Time', null=True, blank=True)
    Voucher_time_value = models.DurationField(verbose_name='Time Value', default=timezone.timedelta(minutes=0), null=True, blank=True, help_text='Time value in minutes.')

    def save(self, *args, **kwargs):
        if self.Voucher_status == 'Used':
             self.Voucher_used_date_time = timezone.now()

        if self.Voucher_status == 'Not Used':
            self.Voucher_used_date_time = None

        super(Vouchers, self).save(*args, **kwargs)

    class Meta:
        verbose_name = 'Voucher'
        verbose_name_plural = 'Vouchers'

    def __str__(self):
        return self.Voucher_code


class Device(models.Model):
    Device_ID = models.CharField(max_length=255, null=True, blank=True)
    Ethernet_MAC = models.CharField(max_length=50, null=True, blank=True)
    Device_SN = models.CharField(max_length=50, null=True, blank=True)
    pub_rsa = models.TextField(null=False, blank=False)
    ca = models.CharField(max_length=200, unique=True, null=False, blank=False)
    action = models.IntegerField(default=0)
    Sync_Time = models.DateTimeField(default=timezone.now, null=True, blank=True)

    class Meta:
        verbose_name = 'Hardware'

    def __str__(self):
        return 'Hardware Settings'

class PushNotifications(models.Model):
    Enabled = models.BooleanField(default=False)
    app_id = models.CharField(verbose_name = "OneSignal App ID", max_length=255, null=True, blank=True)
    api_key = models.CharField(verbose_name="OneSignal API Key", max_length=255, null=True, blank=True)
    notification_title = models.CharField(verbose_name="Notification Title", max_length=255, null=True, blank=True)
    notification_message = models.CharField(verbose_name="Notification Message", max_length=255, null=True, blank=True)
    notification_trigger_time = models.DurationField(verbose_name="Notification Trigger", default=timezone.timedelta(minutes=0), help_text="Notification will fire when time is equal to the specified trigger time. Format: hh:mm:ss", null=True, blank=True)

    class Meta:
        verbose_name = "Push Notifications"

    def __str__(self):
        return "Push Notification Settings"