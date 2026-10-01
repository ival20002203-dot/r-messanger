"""Built-in R-Mes / Localgram username reservation catalog.

The catalog is NOT automatically activated. Control Center shows every candidate
as FREE / OCCUPIED / RESERVED and lets a system administrator reserve selected
categories or paste a custom list.
"""
import re

CATEGORY_LABELS = {
    "system": "Системные",
    "official": "Официальные / бренд",
    "roles": "Должности и подразделения",
    "security": "Безопасность",
    "service": "Сервисы и инфраструктура",
    "channels": "Служебные каналы",
    "popular": "Популярные никнеймы",
    "prestige": "Короткие / статусные",
}

SYSTEM = """
admin administrator admins root system sysadmin superadmin developer developers dev devops webmaster
owner owners founder founders creator creators operator operators service services account accounts user users
localgram localgramapp localgram_admin localgram_support localgram_security localgram_team localgram_news
rmes r_mes rmeschat rmes_chat rmesconnect rmes_connect rmes_help rmes_support rmes_news
official verified verification verify badge staff employee employees team teams bot bots robot api apiadmin
login logout signin signout signup register registration auth oauth sso password passwords passwd reset
settings setting config configuration preferences profile profiles username usernames handle handles
home main index dashboard control controlpanel panel console portal web website app application mobile desktop
status health healthcheck ready readyz healthz ping test testing demo sandbox staging production prod beta alpha
system_message system_messages notification notifications notify mail email smtp imap pop3 exchange
noreply no_reply donotreply do_not_reply postmaster abuse administrator
""".split()

OFFICIAL = """
telegram telegramapp whatsapp whatsappbusiness messenger facebook meta instagram threads tiktok youtube
google gmail chrome android microsoft windows office office365 outlook teams azure onedrive sharepoint
apple iphone ios icloud mac macos openai chatgpt anthropic claude github gitlab bitbucket jira confluence
slack zoom dropbox notion figma adobe oracle java mysql mariadb postgres postgresql redis mongodb elastic
elasticsearch docker kubernetes k8s linux ubuntu debian redhat centos rocky vmware vsphere vcenter esxi
veeam zabbix grafana prometheus nginx apache cisco fortinet fortigate paloalto crowdstrike cloudflare
aws amazon gcp digitalocean hetzner dell hp lenovo asus acer samsung huawei xiaomi nokia intel amd nvidia
texnopark texno_park texnoparkuz texnopark_uz
rmes r_mes rmesconnect rmes_connect akfa akfagroup akfa_group
""".split()

ROLES = """
ceo cto cio ciso cfo coo chro cmo cpo cro president vicepresident vice_president vp chairman chairwoman
director directors general_director managing_director executive executive_director deputy deputy_director
head head_of_department department_head manager managers general_manager senior_manager line_manager
supervisor lead leader teamlead team_lead techlead tech_lead foreman coordinator administrator secretary
assistant executive_assistant reception receptionist office office_manager
hr humanresources human_resources people peopleops people_ops recruitment recruiting recruiter recruiters
talent talent_acquisition payroll compensation benefits learning training academy lnd
finance financial accounting accountant accountants treasury treasurer budget budgeting tax taxes
legal lawyer lawyers counsel general_counsel compliance compliance_officer risk risk_manager audit auditor auditors
sales salesman sales_manager sales_team presales businessdevelopment business_development bd account_manager
marketing marketer marketing_team brand branding pr publicrelations public_relations communications comms
procurement purchasing purchase buyer buyers sourcing supply supplychain supply_chain logistics logistic
warehouse warehouses inventory stock customs import export export_manager
production manufacturing factory factories plant plants workshop operations operations_manager
quality qa qc qualitycontrol quality_control hse ehs safety safety_manager
engineering engineer engineers architecture architect architects design designer designers r_and_d rnd research
product product_manager project project_manager projects program program_manager pmo scrum agile
it informationtechnology information_technology ict tech technology infrastructure infra network networking
network_admin server servers storage backup backups database dba databases helpdesk help_desk support
security infosec cyber cybersecurity soc noc monitoring service_desk servicedesk
""".split()

SECURITY = """
security securityteam security_team infosec informationsecurity information_security cybersecurity cyber
soc socteam soc_team noc noc_team secops sec_ops devsecops incident incidents incidentresponse incident_response
emergency emergencies alert alerts warning warnings report reportabuse report_abuse abuse fraud antifraud
phishing spam antispam malware antivirus defender firewall waf vpn proxy zero_trust zerotrust iam identity
identity_access access accesscontrol access_control permission permissions privilege privileges mfa otp 2fa
token tokens secret secrets key keys certificate certificates cert certs pki encryption encrypted decrypt
password_reset passwordreset recovery recover restore lock unlock block unblock banned suspended
moderator moderators moderation audit auditlog audit_log forensic forensics evidence investigation investigations
privacy dataprotection data_protection dpo policy policies rules terms trust safety compliance
""".split()

SERVICE = """
mail email webmail smtp relay mx autodiscover exchange outlook owa calendar contacts drive storage files file
share sharepoint onedrive ftp sftp ssh rdp vpn dns dhcp ntp ldap ldaps active_directory activedirectory ad
entra azuread azure_ad aad sso oauth saml radius tacacs proxy reverseproxy reverse_proxy loadbalancer
load_balancer gateway gateways router routers switch switches wireless wifi wlan lan wan firewall firewalls
server servers host hosts vm virtualmachine virtual_machine hypervisor esxi vcenter vsphere vmware
backup backups restore repository repo repositories veeam nas san iscsi lun storage database databases db
postgres postgresdb mysql mariadb redis cache queue rabbitmq kafka search elastic elasticsearch
monitor monitoring zabbix prometheus grafana logs logging log syslog siem metrics telemetry uptime statuspage
docker container containers compose kubernetes cluster clusters k8s registry cicd ci cd runner gitlabrunner
gitlab_runner githubactions github_actions deploy deployment release releases build builds artifacts
api gatewayapi webhook webhooks integration integrations automation automations agent agents
""".split()

CHANNELS = """
general everyone all allhands all_hands company corporate official announcements announcement announce
news updates update notices notice information info important urgent emergency
events event calendar meetings meeting conference conferences webinar webinars training trainings
help support helpdesk faq questions question ask feedback suggestions suggestion ideas idea
jobs job careers career vacancies vacancy hiring recruitment onboarding offboarding newhires new_hires
media press newsroom blog blogs social community communities forum forums chat chats group groups channel channels
sales marketing hr finance legal compliance it security infrastructure operations production quality logistics
documents docs document files resources knowledge knowledgebase knowledge_base wiki handbook manuals manual
reports reporting analytics statistics stats dashboard status alerts incidents maintenance maintenances
releases release changelog roadmap projects project products product services service
random lounge off_topic offtopic watercooler water_cooler cafeteria canteen transport shuttle parking
""".split()

POPULAR = """
king queen prince princess boss bigboss big_boss chief legend legendary master mastermind pro professional
vip premium elite top best numberone number_one first one ace champ champion winner lucky star superstar
hero superhero captain commander general major colonel bossman don godfather god mother father
alpha beta sigma omega delta gamma matrix neo trinity morpheus ghost shadow phantom spirit dark darkness
light angel demon devil joker clown batman superman spiderman ironman thor loki hulk thanos avenger avengers
ninja samurai ronin shogun warrior gladiator knight viking pirate assassin sniper hunter ranger stalker
wolf lonewolf lone_wolf tiger lion leopard panther jaguar bear polar fox redfox red_fox eagle falcon hawk
raven crow owl dragon phoenix cobra viper python shark whale orca bull bearcat
hacker hackerman coder programmer developerx devmaster adminx rootx cyber cyberman technoman geek nerd
wizard magic magician oracle prophet genius brain smart smartman professor doctor doc mrrobot robot ai
anonymous anon unknown nobody somebody xman x_man zero null void error fatal killer terminator predator
rockstar rock_star starboy star_girl stargirl badboy bad_boy goodboy good_boy gentleman lady
cool coolguy cool_guy crazy madness savage beast monster titan giant immortal infinity eternal
freedom liberty power strong strongman steel iron gold golden silver diamond black white red blue green
fire flame ice frost storm thunder lightning rain sun moon lunar solar space cosmos galaxy universe
dream dreamer hope love lover heart soul smile happy lucky money cash rich billionaire millionaire
real realone real_one original unique exclusive private public secret hidden silent quiet
online offline active busy available away
alex alexx alexey alexander max maxx maxim sam sammy leo leon john johnny mike michael nick nicky
david dan daniel bob bobby tom tommy jack jake james mark martin roman ryan adam alan andy
""".split()

PRESTIGE = """
boss1 boss01 king1 king01 queen1 vip1 vip01 vip007 pro1 pro01 top1 top01 best1 best01 number1 number01
admin1 admin01 root1 root01 dev1 dev01 ceo1 ceo01 cto1 cto01 cio1 cio01 ciso1 ciso01
one1 one01 ace1 ace01 legend1 legend01 master1 master01 alpha1 alpha01 omega1 omega01
user1 user01 user001 user0001 account1 account01 test1 test01 demo1 demo01 official1 official01
support1 support01 help1 help01 info1 info01 news1 news01 team1 team01 staff1 staff01
zero0 zero1 x001 x007 x999 vip999 pro999 top999 boss999 king999
""".split()

# Carefully generated role/department variants. We intentionally avoid random dictionary words.
VARIANT_BASES = """
admin support help security official team staff owner root developer devops sysadmin moderator bot
ceo cto cio ciso cfo coo director manager hr finance legal sales marketing procurement logistics
production quality engineering project product it infra network server backup database
""".split()

def _variants():
    values=set()
    suffixes=("team","office","dept","department","group","center","centre","admin","manager","lead","head","official")
    prefixes=("my","the","real","official")
    for base in VARIANT_BASES:
        for suffix in suffixes:
            values.add(f"{base}_{suffix}")
        for prefix in prefixes:
            values.add(f"{prefix}_{base}")
        for n in range(1,11):
            values.add(f"{base}{n}")
            values.add(f"{base}{n:02d}")
    return values

def _normalize(value):
    value=(value or "").strip().lower().lstrip("@")
    value=re.sub(r"[^a-z0-9_]+","_",value)
    value=re.sub(r"_+","_",value).strip("_")
    return value[:32]

def builtin_catalog():
    groups={
        "system":SYSTEM,
        "official":OFFICIAL,
        "roles":ROLES,
        "security":SECURITY,
        "service":SERVICE,
        "channels":CHANNELS,
        "popular":POPULAR,
        "prestige":PRESTIGE,
    }
    for value in _variants():
        groups["prestige"].append(value)

    seen=set()
    rows=[]
    for category,values in groups.items():
        for value in values:
            username=_normalize(value)
            # Localgram handles allow 4-32 chars. Keep the catalog aligned with the validator.
            if len(username)<4 or username in seen:
                continue
            seen.add(username)
            rows.append((username,category))
    return sorted(rows,key=lambda x:(x[1],x[0]))

BUILTIN_CATALOG=builtin_catalog()
BUILTIN_MAP=dict(BUILTIN_CATALOG)
