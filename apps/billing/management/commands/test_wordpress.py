from django.core.management.base import BaseCommand
from services.wordpress_service import WordPressService


class Command(BaseCommand):
    help = 'Prueba la conexión con WordPress'

    def handle(self, *args, **options):
        wp_service = WordPressService()
        result = wp_service.test_connection()
        
        if result['success']:
            self.stdout.write(self.style.SUCCESS('✅ Conexión exitosa'))
        else:
            self.stdout.write(self.style.ERROR(f'❌ Error: {result["error"]}'))