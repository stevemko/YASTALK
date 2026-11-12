from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand

from core.models import Event, Language, Service, TeamMember, Testimonial

NAIROBI = ZoneInfo('Africa/Nairobi')


class Command(BaseCommand):
    help = "Seed YasTalk's launch languages, services, team, testimonials and the Phase One launch event."

    def handle(self, *args, **options):
        languages = [
            dict(code='en', name_en='English', native_name='English', flag_emoji='🌍', is_rtl=False, order=1),
            dict(code='am', name_en='Amharic', native_name='አማርኛ', flag_emoji='🇪🇹', is_rtl=False, order=2),
            dict(code='ar', name_en='Arabic', native_name='العربية', flag_emoji='🇸🇦', is_rtl=True, order=3),
            dict(code='fr', name_en='French', native_name='Français', flag_emoji='🇫🇷', is_rtl=False, order=4),
            dict(code='ha', name_en='Hausa', native_name='Harshen Hausa', flag_emoji='🇳🇬', is_rtl=False, order=5),
            dict(code='ln', name_en='Lingala', native_name='Lingála', flag_emoji='🇨🇩', is_rtl=False, order=6),
            dict(code='pt', name_en='Portuguese', native_name='Português', flag_emoji='🇵🇹', is_rtl=False, order=7),
            dict(code='es', name_en='Spanish', native_name='Español', flag_emoji='🇪🇸', is_rtl=False, order=8),
            dict(code='sw', name_en='Swahili', native_name='Kiswahili', flag_emoji='🇰🇪', is_rtl=False, order=9),
            dict(code='yo', name_en='Yoruba', native_name='Yorùbá', flag_emoji='🇳🇬', is_rtl=False, order=10),
        ]
        for lang in languages:
            obj, created = Language.objects.update_or_create(code=lang['code'], defaults=lang)
            self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} language: {obj}"))

        # Earlier seeds shipped an offline-packs card. YasTalk needs a connection, so drop it.
        Service.objects.filter(title='Offline Packs').delete()

        services = [
            dict(icon='mic', title='Voice Translation',
                 description='Speak naturally and hear your words carried over into the other language in real time.',
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
            dict(icon='text', title='Travel Phrasebook',
                 description='Save the phrases you use most, with pronunciation hints and cultural notes for each place you visit.',
                 order=5),
            dict(icon='document', title='Document Translation',
                 description='Upload a document and get a formatted translation back, ready to share.',
                 order=6),
        ]
        for svc in services:
            obj, created = Service.objects.update_or_create(title=svc['title'], defaults=svc)
            self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} service: {obj}"))

        team = [
            dict(
                name='Mirindi Jacques Emmanuel',
                role='Founder & CEO of Mirinova Technologies',
                bio=(
                    'Mr. Jacques Emmanuel Mirindi\n'
                    'Founder & CEO of Mirinova Technologies\n\n'
                    'Entrepreneur and strategist, Jacques Emmanuel Mirindi leads the development of Yas Talk, '
                    'an innovative application designed to break down language barriers and simplify global '
                    'communication through instant, multimodal translation (text, audio, and live calls). '
                    'Under his leadership, the team is committed to building modern, seamless technology that '
                    'is accessible to all.'
                ),
                order=1,
            ),
            dict(
                name='Mirindi Bahati Yasmine Muchepe',
                role='Co-Founder and Communications Manager at Mirinova Technologies',
                bio=(
                    'Mrs. Mirindi Bahati Yasmine Muchepe\n'
                    'Co-Founder and Communications Manager at Mirinova Technologies\n\n'
                    'A communications professional with a strong commitment to social impact, Mirindi Bahati '
                    'Yasmine Muchepe contributes to the development of Yas Talk by drawing on her experience in '
                    'communications, marketing, and community engagement. In her role, she supports the team’s '
                    'vision of creating an innovative platform that brings people closer together and facilitates '
                    'communication across language barriers.'
                ),
                order=2,
            ),
            dict(
                name='Collins Ogega Mogoi (Cory)',
                role='Lead Developer',
                bio=(
                    'Collins Ogega Mogoi, professionally known as Cory, is a full-stack web and mobile application '
                    'developer and cybersecurity specialist. Through his company, CoryTech, he delivers scalable '
                    'software and secure infrastructure solutions. As Lead Developer for YasTalk, Cory manages the '
                    'platform’s technical architecture and its global expansion.'
                ),
                order=3,
            ),
            dict(
                name='Stephen Maina',
                role='Developer & Lead Marketer (Kenya)',
                bio=(
                    'Stephen Maina is a versatile Full Stack Web Developer with a strong background in Computer '
                    'Science. He designs and builds responsive websites and apps that combine sleek visuals with '
                    'powerful functionality. He works with Yas Talk as a developer and lead marketer in Kenya.'
                ),
                order=4,
            ),
            dict(
                name='Mohamad F. Arabi',
                role='Community Manager (Kenya)',
                bio=(
                    'Mohamad F. Arabi is a Board Member, Management Consultant, and Business Development Advisor '
                    'with extensive cross-sector experience across Lebanon, the United States, Canada, UK and Africa. '
                    'He brings a strategic approach to governance, organizational development and stakeholder engagement.'
                ),
                order=5,
            ),
        ]
        for member in team:
            obj, created = TeamMember.objects.update_or_create(name=member['name'], defaults=member)
            self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} team: {obj}"))

        sw = Language.objects.filter(code='sw').first()
        ln = Language.objects.filter(code='ln').first()
        ar = Language.objects.filter(code='ar').first()
        ha = Language.objects.filter(code='ha').first()
        yo = Language.objects.filter(code='yo').first()

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
            dict(author_name='Fatima B.', author_role='Kano, Nigeria', language=ha,
                 quote='Ina iya yin magana da abokin kasuwanci na a Legas ba tare da na juya zuwa Turanci ba.',
                 order=4),
            dict(author_name='Tunde O.', author_role='Lagos, Nigeria', language=yo,
                 quote='Mo le ba olugbaja mi sọrọ ni Yorùbá, èmi ò sì ní fi èdè mìíràn ṣe àfikún.',
                 order=5),
        ]
        for t in testimonials:
            obj, created = Testimonial.objects.update_or_create(author_name=t['author_name'], defaults=t)
            self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} testimonial: {obj}"))

        launch, created = Event.objects.update_or_create(
            slug='yastalk-app-phase-one-launch',
            defaults=dict(
                title='YasTalk App Phase One — Official Launch',
                kind=Event.Kind.LAUNCH,
                summary='The day YasTalk Phase One meets the world, live in every launch language.',
                description=(
                    'On Wednesday, 20 January, YasTalk takes its first full step into the world. '
                    'Phase One is our official launch, and you are warmly invited.\n\n'
                    'We will introduce the live languages one by one, show text, voice, camera, conversation and '
                    'document translation working side by side, and share honestly where Phase Two is headed. '
                    'Founders, the build team and early users will be in the room to answer your questions.\n\n'
                    'The launch streams live on our social media platforms, where the stream will be pinned at the '
                    'top of each page when we go on air. Invitations are being sent to guests, and the Nairobi '
                    'venue will be announced here as soon as it is confirmed.\n\n'
                    'Come and talk with us. This is the day the conversation opens.'
                ),
                location='Nairobi, Kenya — venue announced soon',
                image='',
                starts_at=datetime(2027, 1, 20, 10, 0, tzinfo=NAIROBI),
                ends_at=datetime(2027, 1, 20, 11, 0, tzinfo=NAIROBI),
                is_published=True,
            ),
        )
        self.stdout.write(self.style.SUCCESS(
            f"{'Created' if created else 'Updated'} event: {launch} ({launch.starts_at:%d %b %Y})"
        ))

        self.stdout.write(self.style.SUCCESS('Seed data loaded.'))
