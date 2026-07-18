from django.core.management.base import BaseCommand
from core.models import Language, Service, Testimonial


class Command(BaseCommand):
    help = "Seed the database with YasTalk's initial 5 languages, services, and sample testimonials."

    def handle(self, *args, **options):
        languages = [
            dict(code='en', name_en='English', native_name='English', flag_emoji='🇬🇧', is_rtl=False, order=1),
            dict(code='fr', name_en='French', native_name='Français', flag_emoji='🇫🇷', is_rtl=False, order=2),
            dict(code='ln', name_en='Lingala', native_name='Lingála', flag_emoji='🇨🇩', is_rtl=False, order=3),
            dict(code='sw', name_en='Swahili', native_name='Kiswahili', flag_emoji='🇰🇪', is_rtl=False, order=4),
            dict(code='ar', name_en='Arabic', native_name='العربية', flag_emoji='🇸🇦', is_rtl=True, order=5),
        ]
        for lang in languages:
            obj, created = Language.objects.update_or_create(code=lang['code'], defaults=lang)
            self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} language: {obj}"))

        services = [
            dict(icon='mic', title='Voice Translation',
                 description='Speak naturally and hear your words carried over into any of our five languages in real time.',
                 order=1),
            dict(icon='text', title='Text Translation',
                 description='Paste or type any message and get an accurate, context-aware translation instantly.',
                 order=2),
            dict(icon='chat', title='Live Conversation Mode',
                 description='Hold a two-way conversation with someone who speaks a different language, turn by turn.',
                 order=3),
            dict(icon='camera', title='Camera Translation',
                 description='Point your camera at a sign, menu, or document and see the translation overlaid instantly.',
                 order=4),
            dict(icon='offline', title='Offline Packs',
                 description='Download a language pack before you travel and keep translating without any signal.',
                 order=5),
            dict(icon='document', title='Document Translation',
                 description='Upload a document and get a formatted translation back, ready to share.',
                 order=6),
        ]
        for svc in services:
            obj, created = Service.objects.update_or_create(title=svc['title'], defaults=svc)
            self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} service: {obj}"))

        sw = Language.objects.filter(code='sw').first()
        ln = Language.objects.filter(code='ln').first()
        ar = Language.objects.filter(code='ar').first()

        testimonials = [
            dict(author_name='Amina K.', author_role='Nairobi, Kenya', language=sw,
                 quote='YasTalk let me talk to my supplier in Kinshasa without either of us switching to English.',
                 order=1),
            dict(author_name='Jean-Paul M.', author_role='Kinshasa, DRC', language=ln,
                 quote='Nasepeli Lingala mpe azali koyoka na Falansé na tango moko. Ezali kokamwisa!',
                 order=2),
            dict(author_name='Yousef A.', author_role='Cairo, Egypt', language=ar,
                 quote='ترجمة فورية ودقيقة، حتى في المكالمات الصوتية. غيّرت طريقة تواصلي مع فريقي.',
                 order=3),
        ]
        for t in testimonials:
            obj, created = Testimonial.objects.update_or_create(author_name=t['author_name'], defaults=t)
            self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} testimonial: {obj}"))

        self.stdout.write(self.style.SUCCESS('Seed data loaded.'))
