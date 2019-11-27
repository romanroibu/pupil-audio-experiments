def get_user_selected_input_name() -> str:
    from pupil_audio.utils.pyaudio import get_all_inputs, get_default_input

    input_names = sorted(device.name for device in get_all_inputs().values())
    default_name = get_default_input().name

    print("-" * 80)
    print("PLEASE SELECT INPUT DEVICE:")

    for index, name in enumerate(input_names):
        default_flag = "D" if name == default_name else " "
        print(f"\t[{index}] {default_flag}: {name}")

    try:
        selected_name = input_names[int(input(">>> "))]
    except (ValueError, IndexError):
        print("Invalid input device number. Try again.")
        exit(-1)

    print("-" * 80)

    return selected_name


def get_output_file_path(*parts, extension="mp4") -> str:
    import pathlib

    path = pathlib.Path(__file__).parent
    path = path.joinpath("outputs")

    for part in parts:
        path = path.joinpath(part)

    path = path.with_suffix(f".out.{extension}")
    path = path.absolute()

    path.parent.mkdir(parents=True, exist_ok=True)

    return str(path)
