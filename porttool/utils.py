from pathlib import Path

class proputil:
    def __init__(self, propfile: str):
        proppath = Path(propfile)
        if proppath.exists():
            self.propfd = Path(propfile).open('r+')
        else:
            raise FileExistsError(f"File {propfile} does not exist!")
        self.prop = self.__loadprop

    @property
    def __loadprop(self) -> list:
        return self.propfd.readlines()

    def getprop(self, key: str) -> str | None:
        '''
        recive key and return value or None
        '''
        for i in self.prop:
            if key in i: return i.rstrip().split('=')[1]
        return None
    
    def setprop(self, key, value) -> None:
        flag: bool = False # maybe there is not only one item
        for index, current in enumerate(self.prop):
            if key in current:
                self.prop[index] = current.split('=')[0] + '=' + value + '\n'
                flag = True
        if not flag:
            self.prop.append(
                key + '=' + value + '\n'
            )

    def save(self):
        self.propfd.seek(0, 0)
        self.propfd.truncate()
        self.propfd.writelines(self.prop)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb): # with proputil('build.prop') as p:
        self.save()
        self.propfd.close()
