from django.core.management.base import BaseCommand
from apps.core.utils import encrypt_email


class Command(BaseCommand):
    help = 'Encripta un email para uso en URLs'

    def add_arguments(self, parser):
        parser.add_argument(
            'email',
            type=str,
            help='Email a encriptar'
        )

    def handle(self, *args, **options):
        email = options['email']
        
        try:
            encrypted = encrypt_email(email)
            self.stdout.write(
                self.style.SUCCESS(f'Email encriptado: {encrypted}')
            )
            self.stdout.write(
                self.style.WARNING(f'URL: /{encrypted}/cambiar-metodo-pago/')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error encriptando email: {e}')
            )