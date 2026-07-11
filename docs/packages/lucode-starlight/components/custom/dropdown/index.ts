// partially from https://starwind.dev/docs/components/dropdown/

import Dropdown from './Dropdown.astro';
import DropdownContent from './DropdownContent.astro';
import DropdownItem from './DropdownItem.astro';
import DropdownLabel from './DropdownLabel.astro';
import DropdownSeparator from './DropdownSeparator.astro';
import DropdownShortcut from './DropdownShortcut.astro';
import DropdownTrigger from './DropdownTrigger.astro';

export {
    Dropdown,
    DropdownContent,
    DropdownItem,
    DropdownLabel,
    DropdownSeparator,
    DropdownShortcut,
    DropdownTrigger,
};

export default {
    Root: Dropdown,
    Trigger: DropdownTrigger,
    Content: DropdownContent,
    Item: DropdownItem,
    Label: DropdownLabel,
    Separator: DropdownSeparator,
    Shortcut: DropdownShortcut,
};
