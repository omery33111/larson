


export interface Register {
    username: string;
    password: string;
    email: string;
}


export interface Login {
    username: string;
    password: string;
}


export interface MyToken {
    username: string;
    is_staff: Boolean;
}
