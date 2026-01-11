# utils/currency_utils.py
import requests

class CurrencyConfig:
    """Currency configuration for different countries"""
    
    CURRENCIES = {
        'KE': {
            'code': 'KSH',
            'name': 'Kenyan Shilling',
            'symbol': 'KSh',
            'rate_to_ugx': 30,  # 1 KSH = 30 UGX
            'min_deposit': 10,  # KSH
            'min_withdrawal': 50,  # KSH
            'jackpot_min': 100,  # KSH
            'signup_bonus': 200,  # KSH
            'referral_reward': 300,  # KSH
        },
        'UG': {
            'code': 'UGX',
            'name': 'Ugandan Shilling',
            'symbol': 'UGX',
            'rate_to_ugx': 1,
            'min_deposit': 5000,
            'min_withdrawal': 1000,
            'jackpot_min': 5000,
            'signup_bonus': 2500,
            'referral_reward': 10000,
        },
        'DEFAULT': {
            'code': 'UGX',
            'name': 'Ugandan Shilling',
            'symbol': 'UGX',
            'rate_to_ugx': 1,
            'min_deposit': 5000,
            'min_withdrawal': 1000,
            'jackpot_min': 5000,
            'signup_bonus': 2500,
            'referral_reward': 10000,
        }
    }
    
    @classmethod
    def get_currency_config(cls, country_code):
        """Get currency config for a country"""
        return cls.CURRENCIES.get(country_code, cls.CURRENCIES['DEFAULT'])
    
    @classmethod
    def convert_to_base(cls, amount, country_code):
        """Convert local currency to base currency (UGX)"""
        config = cls.get_currency_config(country_code)
        return int(amount * config['rate_to_ugx'])
    
    @classmethod
    def convert_from_base(cls, amount, country_code):
        """Convert base currency (UGX) to local currency"""
        config = cls.get_currency_config(country_code)
        return int(amount / config['rate_to_ugx'])

def detect_country_from_ip(ip_address):
    """
    Detect country from IP address using ip-api.com (free, no key required)
    Returns country code like 'KE', 'UG', etc.
    """
    if not ip_address or ip_address == '127.0.0.1':
        return 'DEFAULT'
    
    try:
        response = requests.get(
            f'http://ip-api.com/json/{ip_address}',
            timeout=3
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                return data.get('countryCode', 'DEFAULT')
    except Exception as e:
        print(f"IP detection error: {e}")
    
    return 'DEFAULT'

def get_user_country(request):
    """
    Get user's country from request headers or IP
    """
    # Try to get from X-Country header (if frontend sends it)
    country = request.headers.get('X-Country')
    if country:
        return country
    
    # Get IP address from request
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip:
        ip = ip.split(',')[0].strip()
    
    return detect_country_from_ip(ip)