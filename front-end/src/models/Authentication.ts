


export interface Register {
    username: string;
    password: string;
    email: string;

    // The tick box on the form. The server refuses the registration without it, so it is part
    // of what a registration is rather than a detail of the screen.
    accepted_terms: boolean;
}


export interface Login {
    username: string;
    password: string;

    // "Stay signed in on this browser". Never sent to the server: it decides which storage
    // holds the pair, and the server issues the same pair either way.
    remember: boolean;
}


export interface MyToken {
    username: string;
    is_staff: Boolean;
}
