
from panda3d.core import Vec3

from Section2SpaceflightDocking.GameObject import *
from Section2SpaceflightDocking.Trigger import Trigger
from Section2SpaceflightDocking.Spawner import Spawner
import Section2SpaceflightDocking.SpecificEnemies as SpecificEnemies

from Section2SpaceflightDocking.Common import Common

from panda3d.core import TextNode

class Level():
    def __init__(self, levelFile):
        self.levelFile = levelFile

        self.geometry = Common.framework.showBase.loader.loadModel("../Section2SpaceflightDocking/Levels/" + levelFile)
        self.geometry.reparentTo(Common.framework.showBase.render)

        try:
            moduleObj = __import__("../Section2SpaceflightDocking.Scripts.{0}".format(levelFile), levelFile)
            if moduleObj is not None:
                self.scriptObj = getattr(moduleObj, levelFile)
        except ImportError as e:
            print ("Error importing script-file" + "Scripts." + levelFile)
            print (e)

        self.enemies = []

        self.deadEnemies = []

        self.particleSystems = []

        self.blasts = []

        self.projectiles = []

        self.passiveObjects = []

        self.items = []

        self.triggers = []

        self.explosions = []

        self.spawners = {}
        self.spawnerGroups = {}

        self.registeredSpawnables = {}

        if hasattr(SpecificEnemies, "spawnableDict"):
            for name, data in SpecificEnemies.spawnableDict.items():
                self.registeredSpawnables[name] = (data, True)

        self.geometryInterpreters = {
            "spawner" : self.buildSpawners,
            "trigger" : self.buildTriggers
        }

        if hasattr(SpecificEnemies, "buildDict"):
            for name, callback in SpecificEnemies.buildDict.items():
                self.geometryInterpreters[name] = callback

        self.spawnersToActivate = []

        self.interpretGeometry()

        for spawnerName in self.spawnersToActivate:
            self.activateSpawner(spawnerName)

        self.spawnersToActivate = []

    def interpretGeometry(self):
        for key, callback in self.geometryInterpreters.items():
            nps = self.geometry.findAllMatches("**/={0}".format(key))
            callback(self, nps)

    def buildSpawners(self, level, spawnerNPs):
        for np in spawnerNPs:
            id = np.getTag("id")
            spawnerIsActive = np.getTag("active") == "True"
            spawnerGroupName = np.getTag("groupName")
            pos = np.getPos(Common.framework.showBase.render)
            h = np.getH(Common.framework.showBase.render)
            spawnerName = np.getName()

            np.removeNode()

            spawnableData, isEnemy = self.registeredSpawnables[id]
            spawner = Spawner(spawnableData, pos, h, isEnemy)

            self.spawners[spawnerName] = spawner
            if spawnerGroupName is not None and len(spawnerGroupName) > 0:
                if spawnerGroupName not in self.spawnerGroups:
                    self.spawnerGroups[spawnerGroupName] = []
                self.spawnerGroups[spawnerGroupName].append(spawner)

            if spawnerIsActive:
                self.spawnersToActivate.append(spawnerName)

    def activateSpawner(self, spawnerName):
        spawner = self.spawners.get(spawnerName, None)
        if spawner is not None:
            self.activateSpawnerInternal(spawner)

    def activateSpawnerInternal(self, spawner):
        if not spawner.isReady:
            return

        obj = spawner.spawnObj
        spawner.spawnObj = None
        spawner.isReady = False

        if spawner.objIsEnemy:
            self.enemies.append(obj)
            #obj.actor.play("spawn")
        else:
            if obj.auraName is not None:
                auraPath = "../Section2SpaceflightDocking/Models/Items/{0}".format(obj.auraName)
            else:
                auraPath = None
            item = Item(obj.root.getPos() + Vec3(0, 0, 1), auraPath, obj)
            self.items.append(item)
        obj.root.wrtReparentTo(Common.framework.showBase.render)

    def activateSpawnerGroup(self, groupName):
        spawnerList = self.spawnerGroups.get(groupName, None)
        if spawnerList is not None:
            for spawner in spawnerList:
                self.activateSpawnerInternal(spawner)

    def buildTriggers(self, level, triggerNPs):
        for np in triggerNPs:
            callbackName = np.getTag("callback")
            onlyOnce = np.getTag("onlyOnce") == "True"
            active = np.getTag("active") == "True"
            trigger = Trigger(callbackName, np, onlyOnce, active)
            self.triggers.append(trigger)

    def triggerActivated(self, trigger):
        if hasattr(self.scriptObj, trigger.callbackName):
            getattr(self.scriptObj, trigger.callbackName)(self)
        if trigger.onlyOnce:
            trigger.active = False

    def addBlast(self, model, minSize, maxSize, duration, pos):
        blast = Blast(model, minSize, maxSize, duration)
        blast.model.reparentTo(Common.framework.showBase.render)
        blast.model.setPos(pos)
        self.blasts.append(blast)
        blast.update(0)
    
    def update(self, player, keyMap, dt):
        if player is not None:
            if player.health > 0:
                # Player update

                player.update(keyMap, dt)

                # Enemy update

                [enemy.update(player, dt) for enemy in self.enemies]

                newlyDeadEnemies = [enemy for enemy in self.enemies if enemy.health <= 0]
                self.enemies = [enemy for enemy in self.enemies if enemy.health > 0]

                for enemy in newlyDeadEnemies:
                    enemy.onDeath()

                self.deadEnemies += newlyDeadEnemies

                enemiesAnimatingDeaths = []
                for enemy in self.deadEnemies:
                    GameObject.update(enemy, dt)
                    enemy.cleanup()
                self.deadEnemies = enemiesAnimatingDeaths

                # Projectile update

                [proj.update(dt) for proj in self.projectiles]

                [proj.cleanup() for proj in self.projectiles if proj.maxHealth > 0 and proj.health <= 0]
                self.projectiles = [proj for proj in self.projectiles if proj.maxHealth <= 0 or proj.health > 0]

                # Passive object update

                [obj.update(dt) for obj in self.passiveObjects]

                [blast.update(dt) for blast in self.blasts]

                [blast.cleanup() for blast in self.blasts if blast.timer <= 0]
                self.blasts = [blast for blast in self.blasts if blast.timer > 0]

                [explosion.update(dt) for explosion in self.explosions]
                [explosion.cleanup() for explosion in self.explosions if not explosion.isAlive()]
                self.explosions = [explosion for explosion in self.explosions if explosion.isAlive()]

        [system.update(dt) for system in self.particleSystems]

    def cleanup(self):
        for blast in self.blasts:
            blast.cleanup()
        self.blasts = []

        for trigger in self.triggers:
            trigger.cleanup()
        self.triggers = []

        for spawner in self.spawners.values():
            spawner.cleanup()
        self.spawners = {}
        self.spawnerGroups = {}

        for enemy in self.enemies:
            enemy.cleanup()
        self.enemies = []

        for enemy in self.deadEnemies:
            enemy.cleanup()
        self.deadEnemies = []

        for passive in self.passiveObjects:
            passive.cleanup()
        self.passiveObjects = []

        for projectile in self.projectiles:
            projectile.cleanup()
        self.projectiles = []