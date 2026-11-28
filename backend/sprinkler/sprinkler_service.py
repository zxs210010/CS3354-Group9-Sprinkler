def add_sprinkler(sprinklers, name, serial_number):
    if serial_number in sprinklers:
        return "Sprinkler already connected"
    sprinklers[serial_number] = {"name": name}
    return "Sprinkler connected successfully"
def rename_sprinkler(sprinklers, serial_number, new_name):
    if serial_number not in sprinklers:
        return "Sprinkler not found"

    sprinklers[serial_number]["name"] = new_name
    return "Sprinkler renamed successfully"

def remove_sprinkler(sprinklers, serial_number):
    if serial_number not in sprinklers:
        return "Sprinkler not found"

    del sprinklers[serial_number]

    return "Sprinkler removed successfully"

