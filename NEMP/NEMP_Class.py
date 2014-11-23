import logging
import re
import requests
import simplejson
import traceback

from distutils.version import LooseVersion
from StringIO import StringIO

from pprint import pprint

logging.getLogger('requests').setLevel(logging.WARNING)

class NotEnoughClasses():
    nemVersions = []

    newMods = False
    mods = {}

    def __init__(self):
        self.requests_session = requests.Session()
        self.requests_session.headers = {
            'User-agent': 'NotEnoughMods:Polling/1.X (+http://github.com/SinZ163/NotEnoughMods)'
        }
        self.requests_session.max_redirects = 5

        self.buildModDict()
        self.QueryNEM()
        self.InitiateVersions()
        self.buildHTML()

    def fetch_page(self, url, timeout=10, decode_json=False):
        try:
            request = self.requests_session.get(url, timeout=timeout)
            if decode_json:
                return request.json()
            else:
                return request.text
        except:
            pass
            # most likely a timeout

    def fetch_json(self, *args, **kwargs):
        return self.fetch_page(*args, decode_json=True, **kwargs)

    def buildModDict(self):
        modList = open("commands/NEMP/mods.json", "r")
        fileInfo = modList.read()
        self.mods = simplejson.loads(fileInfo, strict=False)
        for mod in self.mods:
            if "change" not in self.mods[mod]:
                self.mods[mod]["change"] = "NOT_USED"
            self.mods[mod]['nem'] = []

    def buildHTML(self):
        headerText = ""
        with open("commands/NEMP/header.txt", "r") as f:
            headerText = f.read()
        footerText = ""
        with open("commands/NEMP/footer.txt", "r") as f:
            footerText = f.read()
        with open("commands/NEMP/htdocs/index.html", "w") as f:
            f.write(re.sub("~MOD_COUNT~", str(len(self.mods)), headerText))
            for modName, info in sorted(self.mods.iteritems()):  # TODO: make this not terrible
                if info["active"]:
                    isDisabled = "active"
                else:
                    isDisabled = "disabled"
                f.write("""
        <tr class='{}'>
            <td class='name'>{}</td>""".format(isDisabled, modName))
                f.write("""
            <td class='function'>{}</td>
            <td class='mc_version'>{}</td>
""".format(info["function"], info['nem'][-1]["mc"]))
                try:
                    f.write("            <td class='category'>{}</td>\r\n".format(info["category"]))
                except:
                    pass
                f.write("        </tr>\r\n")
            f.write(footerText)

    def QueryNEM(self):
        try:
            self.nemVersions = reversed(self.fetch_json("http://bot.notenoughmods.com/?json"))
        except:
            print("Failed to get NEM versions, falling back to hard-coded")
            traceb = str(traceback.format_exc())
            print(traceb)
            self.nemVersions = reversed(["1.4.5", "1.4.6-1.4.7", "1.5.1", "1.5.2", "1.6.1", "1.6.2", "1.6.4", "1.7.2"])

    def InitiateVersions(self):
        templist = self.mods.keys()

        try:
            #for MC version in NEM's list
            for version in self.nemVersions:
                #Get the NEM List for this MC Version
                jsonres = self.fetch_json("http://bot.notenoughmods.com/" + version + ".json")

                #For each NEM Mod...
                for mod in jsonres:
                    #Is it in our list?
                    if mod["name"] in templist:
                        mod_info = {'mc': version, 'version': str(mod['version'])}

                        #Does this NEM Mod have a dev version
                        if "dev" in mod and mod["dev"]:
                            #It does
                            mod_info['dev'] = str(mod['dev'])
                        else:
                            #It doesn't
                            mod_info['dev'] = 'NOT_USED'

                        self.mods[mod['name']]['nem'].insert(0, mod_info)

                # ok, so it wasn't directly on the list, is it indirectly on the list though.
                for lonelyMod in templist:
                    #Is this mod a PykerHack(tm)
                    if "name" in self.mods[lonelyMod]:
                        # ok, this is a PykerHack(tm) mod, lets loop through NEM again to find it
                        for lonelyTestMod in jsonres:
                            #Is it here?
                            if self.mods[lonelyMod]["name"] == lonelyTestMod["name"]:
                                # ok, does it exist for this MC version.
                                mod_info = {'mc': version, 'version': str(lonelyTestMod['version'])}

                                #Does it have a dev version
                                if "dev" in lonelyTestMod and lonelyTestMod["dev"]:
                                    #It did
                                    mod_info['dev'] = str(lonelyTestMod['dev'])
                                else:
                                    #It didn't
                                    mod_info['dev'] = 'NOT_USED'

                                self.mods[lonelyMod]['nem'].insert(0, mod_info)

        except:
            pass
            # most likely a timeout

    def CheckJenkins(self, mod):
        jsonres = self.fetch_json(self.mods[mod]["jenkins"]["url"])
        filename = jsonres["artifacts"][self.mods[mod]["jenkins"]["item"]]["fileName"]
        match = re.search(self.mods[mod]["jenkins"]["regex"], filename)
        output = match.groupdict()
        try:
            output["change"] = jsonres["changeSet"]["items"][0]["comment"]
        except:
            pass
        return output

    def CheckMCForge2(self, mod):
        jsonres = self.fetch_json(self.mods[mod]["mcforge"]["url"])

        for promo in jsonres["promos"]:
            if promo == self.mods[mod]["mcforge"]["promo"]:
                return {
                    self.mods[mod]["mcforge"]["promoType"]: jsonres["promos"][promo]["version"],
                    "mc": jsonres["promos"][promo]["mcversion"]
                }
        return {}

    def CheckMCForge(self, mod):
        jsonres = self.fetch_json("http://files.minecraftforge.net/" + self.mods[mod]["mcforge"]["name"] + "/json")
        promotionArray = jsonres["promotions"]
        devMatch = ""
        recMatch = ""
        for promotion in promotionArray:
            if promotion["name"] == self.mods[mod]["mcforge"]["dev"]:
                for entry in promotion["files"]:
                    if entry["type"] == "universal":
                        info = entry["url"]
                        devMatch = re.search(self.mods[mod]["mcforge"]["regex"], info)
            elif promotion["name"] == self.mods[mod]["mcforge"]["rec"]:
                for entry in promotion["files"]:
                    if entry["type"] == "universal":
                        info = entry["url"]
                        recMatch = re.search(self.mods[mod]["mcforge"]["regex"], info)
        if devMatch:
            output = {}
            tmpMC = "null"
            if recMatch:
                output["version"] = recMatch.group(2)
                tmpMC = recMatch.group(1)
            if devMatch.group(1) != tmpMC:
                output["version"] = "NOT_USED"
                output["mc"] = devMatch.group(1)
            else:
                output["mc"] = tmpMC
            output["dev"] = devMatch.group(2)
            return output

    def CheckChickenBones(self, mod):
        result = self.fetch_page("http://www.chickenbones.net/Files/notification/version.php?version=" + self.mods[mod]['nem'][-1]["mc"] + "&file=" + mod)
        if result.startswith("Ret: "):  # Hacky I know, but this is how ChickenBones does it in his mod
            new_version = result[5:]
            if LooseVersion(new_version) > LooseVersion(self.mods[mod]['nem'][-1]['version']):
                return {
                    "version": new_version
                }
            else:
                return {}

    def CheckmDiyo(self, mod):
        result = self.fetch_page("http://tanis.sunstrike.io/" + self.mods[mod]["mDiyo"]["location"])
        lines = result.split()
        result = ""
        for line in lines:
            if ".jar" in line.lower():
                result = line
        match = re.search(self.mods[mod]["mDiyo"]["regex"], result)
        output = match.groupdict()
        return output

    def CheckAE(self, mod):
        jsonres = self.fetch_json("http://ae-mod.info/releases")
        jsonres = sorted(jsonres, key=lambda k: k['Released'])
        relVersion = ""
        #relMC = ""
        devVersion = ""
        devMC = ""
        for version in jsonres:
            if version["Channel"] == "Stable":
                relVersion = version["Version"]
                #relMC = version["Minecraft"]
            else:
                devVersion = version["Version"]
                devMC = version["Minecraft"]
        return {
            "version": relVersion,
            "dev": devVersion,
            "mc": devMC  # TODO: this doesn't seem reliable...
        }

    def CheckAE2(self, mod):
        jsonres = self.fetch_json("http://ae2.ae-mod.info/builds/builds.json")
        jsonres = sorted(jsonres['Versions'], key=lambda k: k['Created'], reverse=True)
        relVersion = ""
        MCversion = ""
        devVersion = ""
        if jsonres[0]["Channel"] == "stable":
            relVersion = jsonres[0]["Version"]
            MCversion = jsonres[0]["VersionMC"]
        else:
            devVersion = jsonres[0]["Version"]
            MCversion = jsonres[0]["VersionMC"]
        if relVersion:
            return {
                "version": relVersion,
                "mc": MCversion
            }
        if devVersion:
            return {
                "dev": devVersion,
                "mc": MCversion
            }

    def CheckDropBox(self, mod):
        result = self.fetch_page(self.mods[mod]["html"]["url"])
        match = None
        for match in re.finditer(self.mods[mod]["html"]["regex"], result):
            pass
        # "match" is still in this scope
        if match:
            match = match.groupdict()

            if 'mc' not in match:
                match['mc'] = self.mods[mod]['nem'][-1]['mc']

            # we already have the 'version', 'dev' and 'mc' fields from the regex
            return match
        else:
            return {}

    def CheckHTML(self, mod):
        result = self.fetch_page(self.mods[mod]["html"]["url"])
        output = {}
        for line in result.splitlines():
            match = re.search(self.mods[mod]["html"]["regex"], line)
            if match:
                output = match.groupdict()
        return output

    def CheckSpacechase(self, mod):
        result = self.fetch_page("http://spacechase0.com/wp-content/plugins/mc-mod-manager/nem.php?mc=" + self.mods[mod]['nem'][-1]["mc"][2:])
        for line in result.splitlines():
            info = line.split(',')
            # 0 = ID, 1=NEM ID, 2=ModID, 3=Author, 4=Link, 5=Version, 6=Comment
            if info[1] == mod:
                return {
                    "version": info[5]
                }
        return {}

    def CheckLunatrius(self, mod):
        jsonres = self.fetch_json("http://mc.lunatri.us/json?latest&mod=" + mod + "&v=2")
        info = jsonres["mods"][mod]["latest"]
        output = {
            "version": info["version"],
            "mc": info["mc"]
        }
        if len(info['changes']) > 0:
            output["change"] = info['changes'][0]
        return output

    def CheckBigReactors(self, mod):
        info = self.fetch_json("http://big-reactors.com/version.json")
        return {
            "dev": info["version"],  # apparently this is a dev build, when it totally isn't.
            "mc": info["mcVersion"]
        }

    def CheckCurse(self, mod):
        modid = self.mods[mod]['curse'].get('id')

        # Accounts for discrepancies between NEM mod names and the Curse link format
        # Uses Curse name if there is one specified. Defaults to the mod's name in lowercase.
        modname = self.mods[mod]['curse'].get('name', mod.lower())

        # As IDs only work with newer mods we have to support two versions of the URL
        if modid:
            jsonres = self.fetch_json("http://widget.mcf.li/mc-mods/minecraft/" + modid + "-" + modname + ".json")
        else:
            jsonres = self.fetch_json("http://widget.mcf.li/mc-mods/minecraft/" + modname + ".json")

        filename = jsonres["download"]["name"]
        match = re.search(self.mods[mod]["curse"]["regex"], filename)
        output = match.groupdict()
        relVersion = ""
        devVersion = ""

        if jsonres["download"]["type"] == "release":
            relVersion = output["version"]
        else:
            devVersion = output["version"]

        MCversion = jsonres["download"]["version"]

        if relVersion:
            return {
                "version": relVersion,
                "mc": MCversion
            }

        if devVersion:
            return {
                "dev": devVersion,
                "mc": MCversion
            }

    def CheckMod(self, mod):
        try:
            # [dev change, version change]
            status = [False, False]

            output = getattr(self, self.mods[mod]["function"])(mod)

            if "mc" in output:
                mc = output['mc']
                mod_info = None
                for elem in self.mods[mod]['nem']:
                    if elem['mc'] == mc:
                        mod_info = elem
                        break
            else:
                mc = self.mods[mod]['nem'][-1]['mc']
                mod_info = self.mods[mod]['nem'][-1]

            if "dev" in output:
                # Remove whitespace at the end and start
                mod_info['dev'] = mod_info['dev'].strip()
                output["dev"] = output["dev"].strip()
                if mod_info['dev'] != output["dev"]:
                    mod_info['dev'] = output["dev"]
                    status[0] = True

            if "version" in output:
                # Remove whitespace at the end and start
                mod_info['version'] = mod_info['version'].strip()
                output["version"] = output["version"].strip()
                if mod_info['version'] != output["version"]:
                    mod_info['version'] = output["version"]
                    status[1] = True

            if "change" in output and "changelog" not in self.mods[mod]:
                self.mods[mod]["change"] = output["change"]

            return status, False  # Everything went fine, no exception raised
        except:
            print(mod + " failed to be polled...")
            traceback.print_exc()
            if 'mc' in locals() and 'mod_info' in locals():
                print 'DEBUG INFO INCOMING. DODGE!'
                print 'MC = %r' % (mc, )
                print 'MOD_INFO = ',
                pprint(mod_info)
                print 'FULL MOD INFO = ',
                pprint(self.mods[mod])
            print
            return [False, False], True  # an exception was raised, so we return a True
