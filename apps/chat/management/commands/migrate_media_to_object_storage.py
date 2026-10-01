from pathlib import Path
from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from apps.accounts.models import User
from apps.chat.models import Attachment,Sticker

class Command(BaseCommand):
    help="Copy existing local MEDIA_ROOT files into configured object storage without changing database file names."

    def add_arguments(self,parser):
        parser.add_argument("--dry-run",action="store_true")
        parser.add_argument("--overwrite",action="store_true")

    def handle(self,*args,**options):
        media_root=Path(settings.MEDIA_ROOT)
        dry=options["dry_run"];overwrite=options["overwrite"];refs=[]
        for obj in User.objects.exclude(avatar="").only("id","avatar"):
            if obj.avatar and obj.avatar.name:refs.append(("avatar",obj.pk,obj.avatar.name))
        for obj in Attachment.objects.exclude(file="").only("id","file"):
            if obj.file and obj.file.name:refs.append(("attachment",obj.pk,obj.file.name))
        for obj in Sticker.objects.exclude(image="").only("id","image"):
            if obj.image and obj.image.name:refs.append(("sticker",obj.pk,obj.image.name))

        seen=set();copied=missing=skipped=failed=0
        for kind,pk,name in refs:
            if name in seen:continue
            seen.add(name);source=media_root/name
            if not source.exists() or not source.is_file():
                missing+=1;self.stderr.write(f"MISSING local source: {name}");continue
            try:exists=default_storage.exists(name)
            except Exception as exc:
                failed+=1;self.stderr.write(f"STORAGE CHECK FAILED {name}: {exc}");continue
            if exists and not overwrite:
                skipped+=1;continue
            if dry:
                copied+=1;self.stdout.write(f"DRY RUN: {name}");continue
            try:
                if exists and overwrite:default_storage.delete(name)
                with source.open("rb") as fh:
                    saved=default_storage.save(name,File(fh,name=Path(name).name))
                if saved!=name:self.stderr.write(f"WARNING storage renamed {name} -> {saved}")
                copied+=1
            except Exception as exc:
                failed+=1;self.stderr.write(f"COPY FAILED {name}: {exc}")
        self.stdout.write(self.style.SUCCESS(
            f"media migration complete: unique={len(seen)} copied={copied} skipped={skipped} missing={missing} failed={failed} dry_run={dry}"
        ))
        if failed:raise SystemExit(2)
