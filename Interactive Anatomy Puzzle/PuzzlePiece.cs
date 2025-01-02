using UnityEngine;
using System.Collections;
using System.Collections.Generic;

public class PuzzlePiece : MonoBehaviour
{
    public int pieceIndex;
    public Vector3 correctPosition;
    public Quaternion correctRotation;
    public bool isSelected = false;
    private bool isSnapped = false;
    private Camera mainCamera;
    private Renderer pieceRenderer;
    public Vector3 snapOffset;
    public float snapThreshold = 1.0f;            // Detection range for snapping
    public float magneticForce = 5.0f;           // How strongly pieces are pulled together
    private bool isInMagneticRange = false;      // Whether the piece is being pulled toward another
    private Vector3 magneticTarget;              // Position being pulled toward
    
    // Grid movement settings
    private float gridSize = 1f;
    private float moveSpeed = 8f;
    private bool isMoving = false;
    private Vector3 targetPosition;
    
    // Rotation settings
    private bool isRotating = false;
    private Quaternion targetRotation;
    private float rotationSpeed = 720f;
    
    // Boundaries for grid movement
    private const float BOUND_X_MIN = -5f;
    private const float BOUND_X_MAX = 5f;
    private const float BOUND_Y_MIN = 1.5f;
    private const float BOUND_Y_MAX = 5f;
    private const float BOUND_Z_MIN = -5f;
    private const float BOUND_Z_MAX = 5f;

    // Add new fields for connected pieces
    private List<PuzzlePiece> connectedPieces = new List<PuzzlePiece>();
    private PuzzlePiece leadPiece; // The piece that controls movement for the group
    
    void Start()
    {
        correctPosition = transform.position;
        correctRotation = transform.rotation;
        
        mainCamera = Camera.main;
        pieceRenderer = GetComponent<Renderer>();
        
        if (pieceRenderer == null)
        {
            Debug.LogError($"No Renderer component found on puzzle piece {gameObject.name}");
        }
        
        RandomizeGridPosition();
        UpdateVisualState();
        targetPosition = transform.position;
        targetRotation = transform.rotation;
        
        gameObject.name = $"Puzzle Piece {pieceIndex}";
    }
    
    void Update()
    {
        if (isSelected && !isSnapped)
        {
            HandleMovementInput();
            HandleRotationInput();
        }
        
        if (isMoving)
        {
            MoveTowardTarget();
        }
        
        if (isRotating)
        {
            RotateTowardTarget();
        }

        // Always check for nearby pieces when not snapped
        if (!isSnapped)
        {
            CheckForNearbyPieces();
        }
    }
    
    void HandleMovementInput()
    {
        if (isMoving || !isSelected || isSnapped) return;
        
        Vector3 movement = Vector3.zero;

        // WASD controls horizontal movement (X and Z axes)
        if (Input.GetKey(KeyCode.W))
        {
            movement.z += moveSpeed * Time.deltaTime;
        }
        else if (Input.GetKey(KeyCode.S))
        {
            movement.z -= moveSpeed * Time.deltaTime;
        }
        else if (Input.GetKey(KeyCode.A))
        {
            movement.x -= moveSpeed * Time.deltaTime;
        }
        else if (Input.GetKey(KeyCode.D))
        {
            movement.x += moveSpeed * Time.deltaTime;
        }

        // Arrow keys control vertical movement (Y axis)
        if (Input.GetKey(KeyCode.UpArrow))
        {
            movement.y += moveSpeed * Time.deltaTime;
        }
        else if (Input.GetKey(KeyCode.DownArrow))
        {
            movement.y -= moveSpeed * Time.deltaTime;
        }

        Vector3 newPosition = transform.position + movement;

        if (IsValidGridPosition(newPosition))
        {
            targetPosition = newPosition;
            isMoving = true;
            
            // Move all connected pieces
            foreach (var piece in connectedPieces)
            {
                piece.targetPosition = newPosition;
                piece.isMoving = true;
            }
        }
    }
    
    void HandleRotationInput()
    {
        if (isRotating || !isSelected || isSnapped) return;
        
        Quaternion? newRotation = null;
        
        if (Input.GetKeyDown(KeyCode.Q)) // Rotate left around Y axis
        {
            newRotation = transform.rotation * Quaternion.Euler(0f, -90f, 0f);
        }
        else if (Input.GetKeyDown(KeyCode.E)) // Rotate right around Y axis
        {
            newRotation = transform.rotation * Quaternion.Euler(0f, 90f, 0f);
        }
        else if (Input.GetKeyDown(KeyCode.R)) // Rotate forward around X axis
        {
            newRotation = transform.rotation * Quaternion.Euler(90f, 0f, 0f);
        }
        else if (Input.GetKeyDown(KeyCode.F)) // Rotate backward around X axis
        {
            newRotation = transform.rotation * Quaternion.Euler(-90f, 0f, 0f);
        }
        else if (Input.GetKeyDown(KeyCode.Z)) // Rotate counterclockwise around Z axis
        {
            newRotation = transform.rotation * Quaternion.Euler(0f, 0f, -90f);
        }
        else if (Input.GetKeyDown(KeyCode.C)) // Rotate clockwise around Z axis
        {
            newRotation = transform.rotation * Quaternion.Euler(0f, 0f, 90f);
        }

        if (newRotation.HasValue)
        {
            targetRotation = newRotation.Value;
            isRotating = true;
            
            // Rotate all connected pieces
            foreach (var piece in connectedPieces)
            {
                piece.targetRotation = newRotation.Value;
                piece.isRotating = true;
            }
        }
    }
    
    void MoveTowardTarget()
    {
        float step = moveSpeed * Time.deltaTime;
        transform.position = Vector3.MoveTowards(transform.position, targetPosition, step);
        
        if (Vector3.Distance(transform.position, targetPosition) < 0.001f)
        {
            transform.position = targetPosition;
            isMoving = false;
        }
    }
    
    void RotateTowardTarget()
    {
        float step = rotationSpeed * Time.deltaTime;
        transform.rotation = Quaternion.RotateTowards(transform.rotation, targetRotation, step);
        
        if (Quaternion.Angle(transform.rotation, targetRotation) < 0.1f)
        {
            transform.rotation = targetRotation;
            isRotating = false;
        }
    }
    
    bool IsValidGridPosition(Vector3 position)
    {
        return position.x >= BOUND_X_MIN && position.x <= BOUND_X_MAX &&
               position.y >= BOUND_Y_MIN - 5f && position.y <= BOUND_Y_MAX + 5f &&
               position.z >= BOUND_Z_MIN && position.z <= BOUND_Z_MAX;
    }
    
    void RandomizeGridPosition()
    {
        float randomX = Mathf.Round(Random.Range(BOUND_X_MIN + 1, BOUND_X_MAX - 1) / gridSize) * gridSize;
        float randomY = Mathf.Round(Random.Range(BOUND_Y_MIN - 3, BOUND_Y_MAX + 3) / gridSize) * gridSize;
        float randomZ = Mathf.Round(Random.Range(BOUND_Z_MIN + 1, BOUND_Z_MAX - 1) / gridSize) * gridSize;
        
        Vector3 randomPosition = new Vector3(
            randomX,
            randomY,
            randomZ
        );
        
        transform.position = randomPosition;
        targetPosition = randomPosition;
        
        int randomRotX = Random.Range(0, 4);
        int randomRotY = Random.Range(0, 4);
        int randomRotZ = Random.Range(0, 4);
        
        transform.rotation = Quaternion.Euler(
            randomRotX * 90f,
            randomRotY * 90f,
            randomRotZ * 90f
        );
        targetRotation = transform.rotation;
    }
    
    void CheckForNearbyPieces()
    {
        if (isSnapped) return;

        PuzzlePiece[] allPieces = FindObjectsByType<PuzzlePiece>(FindObjectsSortMode.None);
        bool foundNearbyPiece = false;

        foreach (var piece in allPieces)
        {
            if (piece != this && !piece.isSnapped)
            {
                float distance = Vector3.Distance(transform.position, piece.transform.position);
                
                // If within snapping range, snap immediately
                if (distance <= 0.5f)  // Immediate snap threshold
                {
                    SnapTogetherWithPiece(piece);
                    return;
                }
                // If within magnetic range, start pulling
                else if (distance <= snapThreshold)
                {
                    foundNearbyPiece = true;
                    isInMagneticRange = true;
                    magneticTarget = piece.transform.position;
                    
                    // Apply magnetic force
                    Vector3 direction = (magneticTarget - transform.position).normalized;
                    float magnetStrength = (snapThreshold - distance) * magneticForce * Time.deltaTime;
                    transform.position += direction * magnetStrength;

                    // If we get very close after moving, snap
                    if (Vector3.Distance(transform.position, piece.transform.position) <= 0.5f)
                    {
                        SnapTogetherWithPiece(piece);
                        return;
                    }
                }
            }
        }

        if (!foundNearbyPiece)
        {
            isInMagneticRange = false;
        }
    }

    void SnapTogetherWithPiece(PuzzlePiece otherPiece)
    {
        // Snap to exact position
        Vector3 snapPosition = (transform.position + otherPiece.transform.position) / 2f;
        transform.position = snapPosition;
        otherPiece.transform.position = snapPosition;
        targetPosition = snapPosition;
        otherPiece.targetPosition = snapPosition;

        // Connect the pieces
        if (!connectedPieces.Contains(otherPiece))
        {
            connectedPieces.Add(otherPiece);
            otherPiece.connectedPieces.Add(this);

            // Connect to other pieces in the group
            foreach (var piece in otherPiece.connectedPieces)
            {
                if (piece != this && !connectedPieces.Contains(piece))
                {
                    connectedPieces.Add(piece);
                    piece.connectedPieces.Add(this);
                    piece.transform.position = snapPosition;
                    piece.targetPosition = snapPosition;
                }
            }

            // Update positions of all connected pieces
            foreach (var piece in connectedPieces)
            {
                piece.transform.position = snapPosition;
                piece.targetPosition = snapPosition;
                piece.isSnapped = true;
                piece.UpdateVisualState();
            }
        }

        // Update states
        isSnapped = true;
        otherPiece.isSnapped = true;
        isInMagneticRange = false;
        otherPiece.isInMagneticRange = false;
        
        // Visual feedback
        UpdateVisualState();
        otherPiece.UpdateVisualState();

        // Notify the puzzle manager
        PuzzleManager manager = FindFirstObjectByType<PuzzleManager>();
        if (manager != null)
        {
            manager.CheckPieceSnapped();
        }
    }

    void UpdateVisualState()
    {
        if (pieceRenderer != null && pieceRenderer.material != null)
        {
            if (isSnapped)
                pieceRenderer.material.color = Color.green;
            else if (isSelected)
                pieceRenderer.material.color = Color.yellow;
            else if (isInMagneticRange)
                pieceRenderer.material.color = new Color(1f, 0.7f, 0f); // Orange for magnetic range
            else
                pieceRenderer.material.color = Color.white;
        }
    }

    public void OnSelected()
    {
        isSelected = true;
        
        // When a piece is selected, select all connected pieces too
        foreach (var piece in connectedPieces)
        {
            piece.isSelected = true;
            piece.UpdateVisualState();
        }
        
        UpdateVisualState();
    }

    public void OnDeselected()
    {
        isSelected = false;
        
        // When a piece is deselected, deselect all connected pieces too
        foreach (var piece in connectedPieces)
        {
            piece.isSelected = false;
            piece.UpdateVisualState();
        }
        
        UpdateVisualState();
    }
    
    public bool IsInCorrectPosition()
    {
        return isSnapped;
    }
}