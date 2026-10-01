import re
from django.conf import settings
from django.core.management.base import BaseCommand
from apps.operations.models import ClientVersionPolicy


def version_tuple(value):
    nums=[int(x) for x in re.findall(r"\d+",str(value or "0"))[:3]]
    return tuple((nums+[0,0,0])[:3])


class Command(BaseCommand):
    help="Synchronize native client version policies from artifacts in CLIENT_UPDATE_DIR."

    def handle(self,*args,**options):
        suffixes={"windows":".exe","android":".apk"}
        changed=0
        for platform,suffix in suffixes.items():
            folder=settings.CLIENT_UPDATE_DIR/platform
            if not folder.exists():
                continue
            candidates=[]
            for path in folder.iterdir():
                if not path.is_file() or path.suffix.lower()!=suffix:
                    continue
                m=re.search(r"(\d+\.\d+(?:\.\d+)?)",path.name)
                if m:candidates.append((version_tuple(m.group(1)),m.group(1),path))
            if not candidates:
                continue
            _,latest,path=sorted(candidates,reverse=True)[0]
            row,created=ClientVersionPolicy.objects.get_or_create(platform=platform,defaults={
                "latest_version":latest,"minimum_version":"12.0.0","enabled":True,
                "release_notes":f"R-Mes {latest}",
            })
            fields=[]
            if version_tuple(row.latest_version)<version_tuple(latest):
                row.latest_version=latest;fields.append("latest_version")
            if not row.enabled:
                row.enabled=True;fields.append("enabled")
            if fields:
                row.save(update_fields=fields+["updated_at"]);changed+=1
            self.stdout.write(self.style.SUCCESS(f"{platform}: {row.latest_version} <- {path.name}"))
        if not changed:
            self.stdout.write("Client version policies are already synchronized.")
